"""5일 90% 가격 범위: 공식, 누수 방지(i ≤ t−5), 표본 부족 시 기본값."""
import numpy as np
import pandas as pd
import pytest

from gold_service.bands import Z_DEFAULT, adaptive_z, compute_bands, forward_return


def _series(n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2022-01-03", periods=n)
    close = pd.Series(1000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx)
    sigma = pd.Series(0.01 + 0.002 * rng.random(n), index=idx)
    return close, sigma


def test_band_formula():
    close, sigma = _series()
    b = compute_bands(close, sigma)
    t = close.index[300]
    sd5 = sigma[t] * np.sqrt(5)
    assert b.loc[t, "band_low"] == pytest.approx(close[t] * np.exp(-b.loc[t, "z"] * sd5))
    assert b.loc[t, "band_high"] == pytest.approx(close[t] * np.exp(b.loc[t, "z"] * sd5))
    assert forward_return(close)[t] == pytest.approx(np.log(close.iloc[305] / close.iloc[300]))


def test_z_matches_pandas_definition():
    close, sigma = _series()
    sd5 = sigma * np.sqrt(5)
    ret5 = forward_return(close)
    expected = (ret5.abs() / sd5).shift(5).rolling(252, min_periods=120).quantile(0.9)
    pd.testing.assert_series_equal(adaptive_z(ret5, sd5), expected, check_names=False)


def test_z_uses_only_settled_errors():
    """t의 z와 범위는 t 이후 종가를 바꿔도 변하지 않는다 (e_i는 i ≤ t−5만 사용)."""
    close, sigma = _series()
    t_pos = 300
    t = close.index[t_pos]
    mod = close.copy()
    mod.iloc[t_pos + 1 :] *= 1.5
    a, b = compute_bands(close, sigma), compute_bands(mod, sigma)
    pd.testing.assert_frame_equal(a.loc[:t, ["z", "band_low", "band_high"]], b.loc[:t, ["z", "band_low", "band_high"]])
    # 반대로 t−4 의 결과(= t+1 종가에 의존)는 바뀐다
    assert a.loc[close.index[t_pos - 4], "ret5"] != b.loc[close.index[t_pos - 4], "ret5"]


def test_default_z_when_too_few_samples():
    close, sigma = _series()
    b = compute_bands(close, sigma)
    # 오차 e_i 120개가 쌓이려면 i ≤ t−5 조건 때문에 t ≥ 124
    assert b["z_is_default"].iloc[:124].all()
    assert (b["z"].iloc[:124] == Z_DEFAULT).all()
    assert not b["z_is_default"].iloc[124:].any()
