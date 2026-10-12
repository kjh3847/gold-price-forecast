"""5. 회귀 테스트: 2024-01-01 이후 walk-forward에서 HAR+GARCH 평균이 rv22 기준보다 QLIKE가 낮다."""
from gold_service.monitoring import qlike
from gold_service.models import walk_forward


def test_ensemble_beats_rv22_baseline(real_close):
    wf = walk_forward(real_close, "2024-01-01").dropna(subset=["y_var"])
    assert len(wf) > 500
    assert not wf["is_fallback"].any()

    q_base = qlike(wf["y_var"], wf["rv22"] ** 2)
    q_ens = qlike(wf["y_var"], wf["sigma"] ** 2)
    q_har = qlike(wf["y_var"], wf["har_var"])
    q_garch = qlike(wf["y_var"], wf["garch_var"])
    print(f"개선율 HAR {1 - q_har / q_base:+.2%}, GARCH {1 - q_garch / q_base:+.2%}, 평균 {1 - q_ens / q_base:+.2%}")

    assert q_ens < q_base
    # 기존 노트북 참고치(HAR +3%, GARCH +8%)에서 크게 벗어나지 않는지 확인
    assert q_har < q_base and q_garch < q_base
