"""2. 재학습 테스트: 학습 행이 i ≤ s−5로 제한되고 63거래일마다 재학습한다."""
import numpy as np
import pytest

from gold_service.features import log_returns
from gold_service.models import (
    RETRAIN_EVERY,
    fit_garch,
    forecast_positions,
    har_training_frame,
    latest_params_as_of,
    needs_retrain,
    train,
)


@pytest.mark.parametrize("s_pos", [300, 450, 650])
def test_har_training_rows_end_at_s_minus_5(synthetic_close, s_pos):
    r = log_returns(synthetic_close)
    X, y = har_training_frame(r, s_pos)
    assert X.index.max() == r.index[s_pos - 5]
    assert (X.index <= r.index[s_pos - 5]).all()
    # 마지막 학습 행의 타깃은 r_{s-4..s}로만 계산된다
    expected = 0.5 * np.log(np.mean(r.iloc[s_pos - 4 : s_pos + 1].values ** 2) + 1e-8)
    assert y.iloc[-1] == pytest.approx(expected)


def test_trained_params_record_cutoff(synthetic_close):
    r = log_returns(synthetic_close)
    p = train(r, 500)
    assert p.trained_on == r.index[500].date()
    assert p.last_train_row == r.index[495].date()


def test_garch_fit_excludes_data_from_s(synthetic_close):
    r = log_returns(synthetic_close)
    s_pos = 500
    r_mod = r.copy()
    r_mod.iloc[s_pos:] *= 5
    assert fit_garch(r, s_pos).params == fit_garch(r_mod, s_pos).params


def test_retrain_every_63_trading_days(synthetic_close):
    r = log_returns(synthetic_close)
    p = train(r, 400)
    assert not needs_retrain(r, 400 + RETRAIN_EVERY - 1, p)
    assert needs_retrain(r, 400 + RETRAIN_EVERY, p)
    assert needs_retrain(r, 400, None)

    _, new = forecast_positions(r, list(range(400, 600)), [])
    positions = [int(r.index.searchsorted(np.datetime64(x.trained_on))) for x in new]
    assert positions == [400, 463, 526, 589]


def test_future_params_are_not_used(synthetic_close):
    r = log_returns(synthetic_close)
    early, late = train(r, 400), train(r, 500)
    assert latest_params_as_of([early, late], r.index[450].date()) is early
    assert latest_params_as_of([early, late], r.index[399].date()) is None
