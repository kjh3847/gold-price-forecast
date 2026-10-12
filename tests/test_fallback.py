"""4. 대체값 테스트: 모델 실패 시 rv22로 대체되고 플래그가 남는다."""
import numpy as np
import pytest

from gold_service import models
from gold_service.features import log_returns, realized_vol


def _boom(*args, **kwargs):
    raise RuntimeError("모델 장애")


def test_predict_failure_falls_back_to_rv22(synthetic_close, monkeypatch):
    r = log_returns(synthetic_close)
    params = models.train(r, 500)
    monkeypatch.setattr(models, "predict_garch_var", _boom)
    fc = models.predict_with_fallback(r, 520, params)
    assert fc.is_fallback
    assert fc.sigma == pytest.approx(realized_vol(r, 22).iloc[520])
    assert "모델 장애" in fc.error


def test_training_failure_falls_back_to_rv22(synthetic_close, monkeypatch):
    r = log_returns(synthetic_close)
    monkeypatch.setattr(models, "fit_garch", _boom)
    forecasts, new_params = models.forecast_positions(r, [500, 501], [])
    assert new_params == []
    assert all(f.is_fallback for f in forecasts)
    assert forecasts[1].sigma == pytest.approx(realized_vol(r, 22).iloc[501])


def test_insufficient_history_falls_back(synthetic_close):
    r = log_returns(synthetic_close)
    forecasts, _ = models.forecast_positions(r, [100], [])  # HAR 학습 행 < 252
    assert forecasts[0].is_fallback
    assert forecasts[0].sigma == pytest.approx(realized_vol(r, 22).iloc[100])


def test_non_finite_prediction_falls_back(synthetic_close, monkeypatch):
    r = log_returns(synthetic_close)
    params = models.train(r, 500)
    monkeypatch.setattr(models, "predict_har_var", lambda *a: np.nan)
    assert models.predict_with_fallback(r, 510, params).is_fallback


def test_success_is_not_flagged(synthetic_close):
    r = log_returns(synthetic_close)
    fc = models.predict_with_fallback(r, 510, models.train(r, 500))
    assert not fc.is_fallback
    assert fc.sigma == pytest.approx(np.sqrt((fc.har_var + fc.garch_var) / 2))
