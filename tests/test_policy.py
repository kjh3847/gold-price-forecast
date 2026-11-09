"""분할 규칙 시뮬레이션·학습·서비스 반영."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from gold_service import db, policy, run_daily
from gold_service.export_json import build_payload
from gold_service.grading import Grade
from gold_service.planner import SPLIT_RULES

from .test_run_daily import MONDAY, settings  # noqa: F401 - fixture 재사용


def week_close(prices_by_week: list[list[float]], start="2024-01-01") -> pd.Series:
    idx = pd.bdate_range(start, periods=5 * len(prices_by_week))
    return pd.Series([p for week in prices_by_week for p in week], index=idx)


def test_equal_amount_avg_cost_is_harmonic_mean():
    assert policy.equal_amount_avg_cost([100, 200]) == pytest.approx(2 / (1 / 100 + 1 / 200))
    assert policy.equal_amount_avg_cost([100, 200], [3, 1]) == pytest.approx(4 / (3 / 100 + 1 / 200))


def test_weekly_samples_use_grade_before_week_and_plan_days():
    close = week_close([[100] * 5, [100, 110, 120, 130, 140]])
    grades = pd.Series([Grade.HIGH] * 10, index=close.index)
    s = policy.weekly_samples(close, grades)
    # 첫 주는 그 전 등급이 없어 제외, 둘째 주만 4개 행동
    assert s["week_start"].nunique() == 1 and sorted(s["n"]) == [1, 2, 3, 5]
    week = s.set_index("n")
    assert week.loc[1, "avg_cost"] == 100  # 월요일
    assert week.loc[3, "avg_cost"] == pytest.approx(policy.equal_amount_avg_cost([100, 120, 140]))
    assert week.loc[5, "timing_error"] < week.loc[1, "timing_error"]
    assert (s["grade"] == "HIGH").all()


def test_holiday_moves_to_next_trading_day_in_week():
    days = list(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"]))  # 월·목 휴장
    assert policy._plan_days(days, [0, 3]) == [days[0], days[2]]


def _samples(errors: dict[str, dict[int, float]], weeks=200) -> pd.DataFrame:
    rows = []
    for w in range(weeks):
        week_start = date(2020, 1, 6) + pd.Timedelta(weeks=w)
        for grade, by_n in errors.items():
            for n, err in by_n.items():
                rows.append({"week_start": week_start, "grade": grade, "n": n, "avg_cost": 1.0, "week_mean": 1.0,
                             "timing_error": err, "source": "history"})
    return pd.DataFrame(rows)


def test_fit_rule_picks_best_reward_per_grade():
    errors = {"LOW": {1: 0.002, 2: 0.0009, 3: 0.0008, 5: 0.0001},
              "NORMAL": {1: 0.006, 2: 0.003, 3: 0.0015, 5: 0.0002},
              "HIGH": {1: 0.009, 2: 0.004, 3: 0.0016, 5: 0.0002},
              "VERY_HIGH": {1: 0.009, 2: 0.004, 3: 0.0016, 5: 0.0002}}
    rule = policy.fit_rule(_samples(errors), cost=0.001, fallback=policy.DEFAULT_RULE)
    # 보상 = −(오차 + 0.001×(n−1))
    assert [len(rule[g]) for g in policy.GRADE_ORDER] == [2, 3, 3, 3]


def test_train_accepts_only_when_holdout_improves_and_monotonic():
    better = {"LOW": {1: 0.002, 2: 0.0009, 3: 0.0008, 5: 0.0001},
              "NORMAL": {1: 0.006, 2: 0.003, 3: 0.0015, 5: 0.0002},
              "HIGH": {1: 0.009, 2: 0.004, 3: 0.0016, 5: 0.0002},
              "VERY_HIGH": {1: 0.009, 2: 0.004, 3: 0.0016, 5: 0.0002}}
    result = policy.train(_samples(better), policy.DEFAULT_RULE, cost=0.001)
    assert result.accepted and result.report["holdout_weeks"] == 52
    assert result.report["holdout_reward_candidate"] > result.report["holdout_reward_current"]

    same = policy.train(_samples(better), result.candidate, cost=0.001)
    assert not same.accepted and "같습니다" in same.reason

    # 낮음에서 5회, 높음에서 1회가 최선인 이상한 데이터 → 단조 조건 위반으로 거절
    weird = {"LOW": {1: 0.01, 2: 0.01, 3: 0.01, 5: 0.0}, "NORMAL": {1: 0.0, 2: 0.01, 3: 0.01, 5: 0.01},
             "HIGH": {1: 0.0, 2: 0.01, 3: 0.01, 5: 0.01}, "VERY_HIGH": {1: 0.0, 2: 0.01, 3: 0.01, 5: 0.01}}
    rejected = policy.train(_samples(weird), policy.DEFAULT_RULE, cost=0.001)
    assert not rejected.accepted and "회차" in rejected.reason


def test_train_uses_log_samples_only_for_training():
    errors = {g: {1: 0.004, 2: 0.002, 3: 0.0015, 5: 0.0002} for g in ("LOW", "NORMAL", "HIGH", "VERY_HIGH")}
    samples = _samples(errors)
    logs = samples[samples["week_start"] == samples["week_start"].max()].assign(source="log")
    result = policy.train(pd.concat([samples, logs]), policy.DEFAULT_RULE, cost=0.001)
    assert result.report["log_samples"] == len(logs)
    assert result.report["holdout_weeks"] == 52


def test_rule_json_roundtrip_and_validation():
    data = policy.rule_to_json(policy.DEFAULT_RULE)
    assert data == {"LOW": [0], "NORMAL": [0, 3], "HIGH": [0, 2, 4], "VERY_HIGH": [0, 1, 2, 3, 4]}
    assert policy.rule_from_json(data) == {g: list(SPLIT_RULES[g]) for g in policy.GRADE_ORDER}
    with pytest.raises(ValueError):
        policy.rule_from_json({**data, "LOW": [1]})
    assert policy.policy_version(policy.DEFAULT_RULE, 0.001) == policy.policy_version(policy.DEFAULT_RULE, 0.001)
    assert policy.policy_version(policy.DEFAULT_RULE, 0.001) != policy.policy_version(policy.DEFAULT_RULE, 0.002)


def test_evaluate_rule_compares_with_lump_and_daily():
    rng = np.random.default_rng(0)
    close = pd.Series(1000 * np.exp(np.cumsum(rng.normal(0, 0.01, 300))), index=pd.bdate_range("2023-01-02", periods=300))
    grades = pd.Series([Grade.NORMAL] * 300, index=close.index)
    m = policy.evaluate_rule(policy.weekly_samples(close, grades), policy.DEFAULT_RULE, 0.001)
    assert m["weeks"] == 59 and m["avg_trades"] == 2
    assert m["daily_timing_error"] < m["timing_error"] < m["lump_timing_error"]
    assert set(m["by_grade"]) == {"보통"}


def test_active_policy_is_used_by_plans_and_payload(settings):  # noqa: F811
    run_daily.run(date(2026, 9, 18), settings)  # 기본 규칙 등록
    engine = db.make_engine(settings.database_url)
    with Session(engine) as session, session.begin():
        default = db.active_policy_row(session)
        default_version = default.version
        assert default.source == "default" and default.metrics["simulation"]["weeks"] > 300
        trained = {Grade.LOW: [0, 3], Grade.NORMAL: [0, 2, 4], Grade.HIGH: [0, 2, 4], Grade.VERY_HIGH: [0, 2, 4]}
        version = policy.policy_version(trained, 0.001)
        db.save_policy(session, version, "trained", policy.rule_to_json(trained), 0.001,
                       {"simulation": None, "training": {"previous_version": default_version}}, activate=True)

    run_daily.run(MONDAY, settings)
    with Session(engine) as session:
        plan = session.query(db.BuyPlan).one()
        grade = Grade(plan.grade)
        assert len(plan.items) == len(trained[grade])
        payload = build_payload(session)
    assert payload["policy"]["version"] == version and payload["policy"]["previous_version"] == default_version
    assert payload["split_rule"]["낮음"] == [0, 3]
    assert payload["model"]["version"].startswith("model-")


def test_force_retrain_trains_on_target_date(settings):  # noqa: F811
    run_daily.run(MONDAY, settings)
    result = run_daily.run(MONDAY, settings, force_retrain=True)
    assert MONDAY in result.retrained
    with Session(db.make_engine(settings.database_url)) as session:
        assert build_payload(session)["model"]["trained_on"] == MONDAY.isoformat()
