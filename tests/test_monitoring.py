from datetime import date

import numpy as np
import pandas as pd
import pytest

from gold_service.monitoring import compute_metrics, qlike, should_alert


def test_qlike_is_zero_for_perfect_forecast():
    y = np.array([1e-4, 2e-4, 3e-4])
    assert qlike(y, y) == pytest.approx(0)
    assert qlike(y, y * 2) > 0


def test_compute_metrics_uses_last_13_weeks_and_realized_only():
    idx = pd.bdate_range("2026-01-01", "2026-06-30")
    sigma = pd.Series(0.01, index=idx)
    realized = pd.Series(0.011**2, index=idx)  # 실제 σ = 예측의 1.1배 → 적중
    realized.iloc[-5:] = np.nan  # 아직 확정 안 됨
    realized.iloc[-10] = 0.02**2  # 2배 → 빗나감
    base = pd.Series(0.02, index=idx)
    m = compute_metrics(date(2026, 6, 30), sigma, realized, base)
    assert m.window_start > date(2026, 3, 30)
    assert m.window_end == realized.dropna().index[-1].date()
    assert m.hit_rate == pytest.approx(1 - 1 / m.n_obs)
    assert m.improvement > 0


def test_alert_after_4_consecutive_negative_weeks():
    assert should_alert([0.1, -0.01, -0.02, -0.03, -0.04])
    assert not should_alert([-0.01, -0.02, 0.01, -0.03])
    assert not should_alert([-0.01, -0.02, -0.03])
    assert not should_alert([-0.01, None, -0.02, -0.03])
