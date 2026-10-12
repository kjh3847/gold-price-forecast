"""수익률·실현변동성(rv) 피처와 학습 타깃.

모든 피처는 날짜 t까지의 수익률만 사용한다. 타깃만 t+1…t+5를 사용한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZON = 5
FEATURE_EPS = 1e-4
TARGET_EPS = 1e-8
HAR_WINDOWS = (1, 5, 22)
HAR_FEATURES = ["log_rv1", "log_rv5", "log_rv22"]


def log_returns(close: pd.Series) -> pd.Series:
    """r_t = log(close_t / close_{t-1}). 첫 행(NaN)은 제거한다."""
    r = np.log(close.astype(float)).diff().dropna()
    r.name = "r"
    return r


def realized_vol(r: pd.Series, window: int) -> pd.Series:
    """최근 window일 r^2 평균의 제곱근. window=1이면 |r_t|."""
    if window == 1:
        return r.abs()
    return np.sqrt((r**2).rolling(window).mean())


def har_features(r: pd.Series) -> pd.DataFrame:
    """HAR 피처: log(rvN + 1e-4), N ∈ {1, 5, 22}."""
    return pd.DataFrame(
        {name: np.log(realized_vol(r, w) + FEATURE_EPS) for name, w in zip(HAR_FEATURES, HAR_WINDOWS)},
        index=r.index,
    )


def forward_variance(r: pd.Series, horizon: int = HORIZON) -> pd.Series:
    """y_t^2 = mean(r_{t+1}^2 … r_{t+h}^2). 미래 h일이 모두 있어야 값이 생긴다."""
    r2 = r**2
    fwd = pd.concat([r2.shift(-k) for k in range(1, horizon + 1)], axis=1)
    return fwd.mean(axis=1, skipna=False).rename("y_var")


def log_target(r: pd.Series, horizon: int = HORIZON) -> pd.Series:
    """HAR 타깃: log(y_t) = 0.5 * log(분산 + 1e-8)."""
    return (0.5 * np.log(forward_variance(r, horizon) + TARGET_EPS)).rename("log_y")
