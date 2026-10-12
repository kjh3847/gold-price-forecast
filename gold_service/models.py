"""변동성 모델: HAR, GARCH(1,1), 앙상블, 대체값, 재학습 스케줄.

검증된 명세를 그대로 구현한다. 모델 종류·하이퍼파라미터를 바꾸지 말 것.
- 예측 대상 σ_t: 날짜 t 종가까지 보고 낸 "다음 5거래일 하루 변동성"
- σ_t = sqrt((HAR 분산 + GARCH 분산) / 2)
- 63거래일마다 재학습, 재학습 시점 s의 HAR 학습 행은 i ≤ s−5
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from arch import arch_model
from sklearn.linear_model import LinearRegression

from gold_service.features import (
    HAR_FEATURES,
    HORIZON,
    forward_variance,
    har_features,
    log_returns,
    log_target,
    realized_vol,
)

log = logging.getLogger(__name__)

RETRAIN_EVERY = 63
MIN_TRAIN_ROWS = 252
GARCH_SCALE = 100.0
GARCH_PARAM_NAMES = ["mu", "omega", "alpha[1]", "beta[1]", "nu"]


class ModelError(RuntimeError):
    """학습·예측 실패. 호출 측에서 대체값으로 전환한다."""


# ---------------------------------------------------------------- 파라미터
@dataclass
class HARParams:
    coef: list[float]
    intercept: float
    resid_var: float


@dataclass
class GARCHParams:
    params: dict[str, float]


@dataclass
class ModelParams:
    trained_on: date  # 학습 기준일 s
    har: HARParams
    garch: GARCHParams
    n_train_rows: int  # HAR 학습 행 수
    last_train_row: date  # HAR 학습에 쓴 마지막 행 날짜 (= s−5 거래일)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trained_on"] = self.trained_on.isoformat()
        d["last_train_row"] = self.last_train_row.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ModelParams":
        return cls(
            trained_on=date.fromisoformat(d["trained_on"]),
            har=HARParams(**d["har"]),
            garch=GARCHParams(**d["garch"]),
            n_train_rows=d["n_train_rows"],
            last_train_row=date.fromisoformat(d["last_train_row"]),
        )


@dataclass
class Forecast:
    date: date
    sigma: float
    is_fallback: bool
    har_var: float | None = None
    garch_var: float | None = None
    rv22: float | None = None
    params_trained_on: date | None = None
    error: str | None = field(default=None, repr=False)


# ---------------------------------------------------------------- HAR
def har_training_frame(r: pd.Series, s_pos: int) -> tuple[pd.DataFrame, pd.Series]:
    """재학습 시점 s(위치 s_pos)에서 쓸 수 있는 HAR 학습 데이터.

    s 이후 데이터를 잘라낸 뒤 타깃을 계산하므로 타깃이 확정된 i ≤ s−5 행만 남는다.
    """
    hist = r.iloc[: s_pos + 1]
    data = har_features(hist).join(log_target(hist)).dropna()
    cutoff = hist.index[s_pos - HORIZON] if s_pos >= HORIZON else None
    if cutoff is None or (len(data) and data.index[-1] > cutoff):
        raise ModelError("HAR 학습 행이 s−5를 넘었습니다 (누수)")
    return data[HAR_FEATURES], data["log_y"]


def fit_har(r: pd.Series, s_pos: int) -> tuple[HARParams, int, pd.Timestamp]:
    X, y = har_training_frame(r, s_pos)
    if len(X) < MIN_TRAIN_ROWS:
        raise ModelError(f"HAR 학습 행 부족: {len(X)} < {MIN_TRAIN_ROWS}")
    reg = LinearRegression().fit(X.values, y.values)
    resid = y.values - reg.predict(X.values)
    params = HARParams(coef=[float(c) for c in reg.coef_], intercept=float(reg.intercept_), resid_var=float(np.var(resid)))
    return params, len(X), X.index[-1]


def predict_har_var(r: pd.Series, t_pos: int, p: HARParams) -> float:
    """HAR 분산 예측 = exp(2·예측값 + 2·잔차분산) (로그정규 편향 보정)."""
    x = har_features(r.iloc[: t_pos + 1]).iloc[-1].values
    if not np.all(np.isfinite(x)):
        raise ModelError("HAR 피처에 결측이 있습니다 (rv22 이력 부족)")
    pred = float(np.dot(p.coef, x) + p.intercept)
    return float(np.exp(2 * pred + 2 * p.resid_var))


# ---------------------------------------------------------------- GARCH
def _garch_model(r_slice: pd.Series):
    return arch_model(r_slice * GARCH_SCALE, mean="Constant", vol="GARCH", p=1, q=1, dist="t")


def fit_garch(r: pd.Series, s_pos: int) -> GARCHParams:
    """s 이전 데이터로 파라미터 추정 (arch의 last_obs=s, s 자체는 제외)."""
    hist = r.iloc[: s_pos + 1]
    res = _garch_model(hist).fit(disp="off", last_obs=hist.index[-1], show_warning=False)
    if res.convergence_flag != 0:
        raise ModelError(f"GARCH 수렴 실패 (flag={res.convergence_flag})")
    return GARCHParams(params={k: float(res.params[k]) for k in GARCH_PARAM_NAMES})


def predict_garch_var(r: pd.Series, t_pos: int, p: GARCHParams) -> float:
    """고정 파라미터로 t까지의 수익률을 반영해 5일 분산 예측의 평균을 구한다."""
    hist = r.iloc[: t_pos + 1]
    values = np.array([p.params[k] for k in GARCH_PARAM_NAMES])
    fc = _garch_model(hist).fix(values).forecast(horizon=HORIZON, reindex=False)
    return float(fc.variance.iloc[-1].mean() / GARCH_SCALE**2)


# ---------------------------------------------------------------- 앙상블·대체값
def train(r: pd.Series, s_pos: int) -> ModelParams:
    har, n_rows, last_row = fit_har(r, s_pos)
    garch = fit_garch(r, s_pos)
    return ModelParams(
        trained_on=r.index[s_pos].date(),
        har=har,
        garch=garch,
        n_train_rows=n_rows,
        last_train_row=last_row.date(),
    )


def predict(r: pd.Series, t_pos: int, params: ModelParams) -> Forecast:
    har_var = predict_har_var(r, t_pos, params.har)
    garch_var = predict_garch_var(r, t_pos, params.garch)
    sigma = float(np.sqrt((har_var + garch_var) / 2))
    if not np.isfinite(sigma) or sigma <= 0:
        raise ModelError(f"비정상 예측값 sigma={sigma}")
    return Forecast(
        date=r.index[t_pos].date(),
        sigma=sigma,
        is_fallback=False,
        har_var=har_var,
        garch_var=garch_var,
        params_trained_on=params.trained_on,
    )


def rv22_at(r: pd.Series, t_pos: int) -> float:
    return float(realized_vol(r.iloc[: t_pos + 1], 22).iloc[-1])


def predict_with_fallback(r: pd.Series, t_pos: int, params: ModelParams | None) -> Forecast:
    """모델 예측, 실패하면 σ = rv22 로 대체하고 플래그를 남긴다."""
    rv22 = rv22_at(r, t_pos)
    try:
        if params is None:
            raise ModelError("학습된 파라미터가 없습니다")
        fc = predict(r, t_pos, params)
    except Exception as exc:  # noqa: BLE001 - 어떤 실패든 대체값으로 전환
        log.warning("예측 실패 → rv22 대체값 사용 (%s): %s", r.index[t_pos].date(), exc)
        if not np.isfinite(rv22) or rv22 <= 0:
            raise ModelError(f"대체값 rv22도 계산할 수 없습니다: {rv22}") from exc
        return Forecast(
            date=r.index[t_pos].date(),
            sigma=rv22,
            is_fallback=True,
            rv22=rv22,
            params_trained_on=params.trained_on if params else None,
            error=str(exc),
        )
    fc.rv22 = rv22
    return fc


# ---------------------------------------------------------------- 재학습 스케줄
def needs_retrain(r: pd.Series, t_pos: int, params: ModelParams | None) -> bool:
    if params is None:
        return True
    trained_pos = int(r.index.searchsorted(pd.Timestamp(params.trained_on)))
    return t_pos - trained_pos >= RETRAIN_EVERY


def latest_params_as_of(history: list[ModelParams], d: date) -> ModelParams | None:
    """d 이전(포함)에 학습된 파라미터 중 가장 최근 것. 미래 파라미터는 쓰지 않는다."""
    eligible = [p for p in history if p.trained_on <= d]
    return max(eligible, key=lambda p: p.trained_on) if eligible else None


def forecast_positions(
    r: pd.Series, positions: list[int], history: list[ModelParams]
) -> tuple[list[Forecast], list[ModelParams]]:
    """주어진 위치들(오름차순)에 대해 필요 시 재학습하며 예측한다.

    반환: (예측 목록, 새로 학습된 파라미터 목록)
    """
    history = list(history)
    new_params: list[ModelParams] = []
    forecasts: list[Forecast] = []
    for t_pos in positions:
        d = r.index[t_pos].date()
        params = latest_params_as_of(history, d)
        if needs_retrain(r, t_pos, params):
            try:
                params = train(r, t_pos)
                history.append(params)
                new_params.append(params)
                log.info("재학습 완료: 기준일 %s, HAR 학습 행 %d (마지막 %s)", d, params.n_train_rows, params.last_train_row)
            except Exception as exc:  # noqa: BLE001
                log.warning("재학습 실패 (%s): %s — 기존 파라미터로 계속", d, exc)
        forecasts.append(predict_with_fallback(r, t_pos, params))
    return forecasts, new_params


def walk_forward(close: pd.Series, start: date | str, end: date | str | None = None) -> pd.DataFrame:
    """start 이후 모든 거래일을 일간 배치와 같은 규칙으로 예측한다 (백테스트·회귀 테스트용).

    close: DatetimeIndex 종가 시계열
    """
    r = log_returns(close)
    mask = r.index >= pd.Timestamp(start)
    if end is not None:
        mask &= r.index <= pd.Timestamp(end)
    positions = [int(i) for i in np.flatnonzero(mask)]
    forecasts, _ = forecast_positions(r, positions, [])
    out = pd.DataFrame([asdict(f) for f in forecasts]).drop(columns=["error"])
    out["date"] = pd.to_datetime(out["date"])
    out = out.set_index("date")
    out["rv22"] = realized_vol(r, 22).reindex(out.index)
    out["y_var"] = forward_variance(r).reindex(out.index)
    return out
