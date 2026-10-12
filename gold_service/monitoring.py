"""주간 모니터링 지표와 경보."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

WINDOW_WEEKS = 13
HIT_TOLERANCE = 0.30
ALERT_CONSECUTIVE = 4
VAR_FLOOR = 1e-12  # 실제 분산이 0이면 log가 발산하므로 하한을 둔다


@dataclass
class MonitoringResult:
    date: date
    window_start: date
    window_end: date
    n_obs: int
    hit_rate: float | None
    qlike_model: float | None
    qlike_baseline: float | None
    improvement: float | None
    alert: bool = False


def qlike(y: np.ndarray, h: np.ndarray) -> float:
    """QLIKE = mean(y/h − log(y/h) − 1). y = 실제 분산, h = 예측 분산."""
    ratio = np.maximum(np.asarray(y, float), VAR_FLOOR) / np.asarray(h, float)
    return float(np.mean(ratio - np.log(ratio) - 1))


def compute_metrics(
    as_of: date,
    sigma: pd.Series,
    realized_var: pd.Series,
    baseline_sigma: pd.Series,
) -> MonitoringResult:
    """as_of 기준 지난 13주 예측 중 실제값이 확정된 것만으로 지표를 계산한다.

    sigma, realized_var, baseline_sigma: 같은 DatetimeIndex (예측 기준일 t).
    realized_var는 as_of까지 확정된 값만 있어야 한다 (나머지 NaN).
    """
    window_start = as_of - timedelta(weeks=WINDOW_WEEKS)
    df = pd.DataFrame({"sigma": sigma, "y": realized_var, "base": baseline_sigma})
    df = df[(df.index > pd.Timestamp(window_start)) & (df.index <= pd.Timestamp(as_of))].dropna()
    if df.empty:
        return MonitoringResult(as_of, window_start, as_of, 0, None, None, None, None)
    hit = (np.abs(np.sqrt(df["y"]) / df["sigma"] - 1) <= HIT_TOLERANCE).mean()
    q_model = qlike(df["y"].values, df["sigma"].values ** 2)
    q_base = qlike(df["y"].values, df["base"].values ** 2)
    return MonitoringResult(
        date=as_of,
        window_start=df.index[0].date(),
        window_end=df.index[-1].date(),
        n_obs=len(df),
        hit_rate=float(hit),
        qlike_model=q_model,
        qlike_baseline=q_base,
        improvement=1 - q_model / q_base,
    )


def should_alert(improvements: list[float | None]) -> bool:
    """최근 4주(이번 주 포함, 시간순 마지막 4개) 개선율이 모두 0% 미만이면 경보."""
    recent = improvements[-ALERT_CONSECUTIVE:]
    return len(recent) == ALERT_CONSECUTIVE and all(v is not None and v < 0 for v in recent)
