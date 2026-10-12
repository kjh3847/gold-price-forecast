"""평가 명령: 기존 노트북 기대값(2024-01 ~ 2026-09)과 가까운지 확인한다."""
import pytest

from gold_service.evaluate import evaluate


@pytest.fixture(scope="module")
def metrics(real_close):
    return evaluate(real_close, "2024-01-01")


def test_matches_notebook_reference(metrics):
    assert metrics["period_start"] == "2024-01-02"
    assert metrics["z_default_days"] == 0 and metrics["fallback_days"] == 0
    assert metrics["hit_rate"] == pytest.approx(0.895, abs=0.01)
    assert metrics["avg_width"] == pytest.approx(0.046, abs=0.003)
    base = metrics["baseline"]
    assert base["hit_rate"] == pytest.approx(0.885, abs=0.01)
    assert base["avg_width"] == pytest.approx(0.045, abs=0.003)


def test_nonoverlap_and_qlike(metrics):
    assert metrics["n_nonoverlap"] == -(-metrics["n_days"] // 5)
    assert 0.8 < metrics["hit_rate_nonoverlap"] <= 1
    assert metrics["qlike_improvement"] > 0
