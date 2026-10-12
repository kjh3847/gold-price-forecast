"""1. 누수 테스트: 날짜 t의 예측은 t+1 이후 데이터를 바꿔도 변하지 않는다."""
import numpy as np
import pandas as pd

from gold_service.features import har_features, log_returns
from gold_service.grading import grade_series
from gold_service.models import forecast_positions, walk_forward


def _perturb_after(close: pd.Series, t: pd.Timestamp, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    out = close.copy()
    future = out.index > t
    out[future] = out[future] * np.exp(rng.normal(0, 0.05, future.sum()))  # 큰 충격
    return out


def test_forecast_at_t_ignores_future(synthetic_close):
    r = log_returns(synthetic_close)
    t_pos = 600
    t = r.index[t_pos]
    r_mod = log_returns(_perturb_after(synthetic_close, t))
    assert not np.allclose(r.iloc[t_pos + 1 :], r_mod.iloc[t_pos + 1 :])

    positions = list(range(540, t_pos + 1))  # 540에서 학습, 603(=540+63)에서 재학습 전
    base, _ = forecast_positions(r, positions, [])
    mod, _ = forecast_positions(r_mod, positions, [])
    assert base[-1].sigma == mod[-1].sigma
    assert base[-1].har_var == mod[-1].har_var
    assert base[-1].garch_var == mod[-1].garch_var
    assert not base[-1].is_fallback


def test_walk_forward_ignores_future_on_real_data(real_close):
    t = pd.Timestamp("2024-06-28")
    base = walk_forward(real_close, "2024-01-01", end=t)
    mod = walk_forward(_perturb_after(real_close, t), "2024-01-01", end=t)
    pd.testing.assert_series_equal(base["sigma"], mod["sigma"])


def test_features_and_grades_ignore_future(synthetic_close):
    r = log_returns(synthetic_close)
    t = r.index[500]
    r_mod = log_returns(_perturb_after(synthetic_close, t))
    pd.testing.assert_frame_equal(har_features(r).loc[:t], har_features(r_mod).loc[:t])

    sigma = r.abs().rolling(22).mean().dropna()
    sigma_mod = sigma.copy()
    sigma_mod[sigma_mod.index > t] *= 10
    pd.testing.assert_frame_equal(grade_series(sigma).loc[:t], grade_series(sigma_mod).loc[:t])
