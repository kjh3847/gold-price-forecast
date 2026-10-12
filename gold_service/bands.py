"""다음 5거래일 90% 가격 범위 (적응형 범위 배수).

- ret5_t = log(close_{t+5} / close_t)
- sd5_t  = σ_t × √5
- e_i    = |ret5_i| / sd5_i
- z_t    = 90% 분위수(e_i), i ≤ t−5 (결과 확정분), 최근 252개, 최소 120개
- 범위   = close_t × exp(∓ z_t × sd5_t)
표본이 부족하면 z = 1.645 를 쓰고 플래그를 남긴다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gold_service.features import HORIZON

COVERAGE = 0.9
Z_WINDOW = 252
Z_MIN_PERIODS = 120
Z_DEFAULT = 1.645  # 정규분포 90% 양측


def forward_return(close: pd.Series, horizon: int = HORIZON) -> pd.Series:
    """ret5_t = log(close_{t+5} / close_t). 아직 확정 안 된 날은 NaN."""
    return np.log(close.shift(-horizon) / close).rename("ret5")


def adaptive_z(ret5: pd.Series, sd5: pd.Series, horizon: int = HORIZON) -> pd.Series:
    """z_t = (|ret5| / sd5).shift(5).rolling(252, min_periods=120).quantile(0.9).

    shift(5) 덕분에 t 시점에는 결과가 확정된 i ≤ t−5 의 오차만 쓴다.
    """
    e = ret5.abs() / sd5
    return e.shift(horizon).rolling(Z_WINDOW, min_periods=Z_MIN_PERIODS).quantile(COVERAGE).rename("z")


def compute_bands(close: pd.Series, sigma: pd.Series) -> pd.DataFrame:
    """sigma의 각 날짜에 대한 z, 범위 하한·상한, 기본값 사용 플래그.

    close: 종가 (sigma.index 를 포함하고, 그 이후 5거래일까지 있으면 오차 계산에 쓰인다)
    sigma: 예측 기준일별 σ_t (연속된 거래일, 오름차순)
    """
    close_t = close.reindex(sigma.index)
    sd5 = sigma * np.sqrt(HORIZON)
    # 같은 거래일 축에서 ret5를 계산해야 shift(5)가 "5거래일 전"을 뜻한다
    ret5 = forward_return(close).reindex(sigma.index)
    z = adaptive_z(ret5, sd5)
    is_default = z.isna()
    z = z.fillna(Z_DEFAULT)
    return pd.DataFrame(
        {
            "z": z,
            "z_is_default": is_default,
            "band_low": close_t * np.exp(-z * sd5),
            "band_high": close_t * np.exp(z * sd5),
            "sd5": sd5,
            "ret5": ret5,
        },
        index=sigma.index,
    )


def half_width(band_low, band_high, close):
    """범위 반폭(±비율) = (상한 − 하한) / (2 × 종가)."""
    return (band_high - band_low) / (2 * close)
