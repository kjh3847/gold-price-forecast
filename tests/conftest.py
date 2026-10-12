from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATA_CSV = Path(__file__).resolve().parent.parent / "data" / "gold_only_ready.csv"


@pytest.fixture(scope="session")
def real_close() -> pd.Series:
    df = pd.read_csv(DATA_CSV, encoding="utf-8-sig", usecols=["date", "gold"], parse_dates=["date"])
    return df.set_index("date")["gold"].rename("close")


def simulate_close(n: int = 700, seed: int = 0) -> pd.Series:
    """GARCH(1,1) 형태의 합성 종가 시계열 (영업일 인덱스)."""
    rng = np.random.default_rng(seed)
    omega, alpha, beta = 2e-6, 0.06, 0.92
    var = omega / (1 - alpha - beta)
    r = np.empty(n)
    for i in range(n):
        r[i] = np.sqrt(var) * rng.standard_t(6) / np.sqrt(1.5)
        var = omega + alpha * r[i] ** 2 + beta * var
    idx = pd.bdate_range("2020-01-01", periods=n + 1)
    return pd.Series(1000 * np.exp(np.concatenate([[0], np.cumsum(r)])), index=idx, name="close")


@pytest.fixture
def synthetic_close() -> pd.Series:
    return simulate_close()
