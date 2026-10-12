"""σ_t → 백분위 → 변동성 등급."""
from __future__ import annotations

from enum import Enum

import numpy as np
import pandas as pd

PERCENTILE_WINDOW = 252
MIN_HISTORY = 60


class Grade(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

    @property
    def label(self) -> str:
        return {"LOW": "낮음", "NORMAL": "보통", "HIGH": "높음", "VERY_HIGH": "매우 높음"}[self.value]


def percentile_of_last(values: np.ndarray | list[float]) -> float | None:
    """마지막 값이 (자기 자신 포함) 최근 252개 안에서 차지하는 백분위(0~100).

    values는 시간순이며 마지막 원소가 오늘 값이다. 미래 값은 넘기지 않는다.
    이력이 60개 미만이면 None.
    """
    window = np.asarray(values, dtype=float)[-PERCENTILE_WINDOW:]
    if len(window) < MIN_HISTORY:
        return None
    return float((window <= window[-1]).mean() * 100)


def grade_from_percentile(pct: float | None) -> Grade | None:
    if pct is None:
        return None
    if pct <= 33:
        return Grade.LOW
    if pct <= 67:
        return Grade.NORMAL
    if pct <= 90:
        return Grade.HIGH
    return Grade.VERY_HIGH


def grade_series(sigma: pd.Series) -> pd.DataFrame:
    """시계열 전체에 대해 각 날짜의 백분위·등급을 그날까지의 값만으로 계산한다."""
    values = sigma.to_numpy(dtype=float)
    pcts = [percentile_of_last(values[: i + 1]) for i in range(len(values))]
    return pd.DataFrame(
        {"percentile": pcts, "grade": [grade_from_percentile(p) for p in pcts]},
        index=sigma.index,
    )
