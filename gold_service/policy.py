"""분할 규칙(등급 → 몇 번, 어느 요일) 시뮬레이션과 학습.

금값 방향은 예측하지 않으므로 "분할로 더 싸게 샀는가"는 평균적으로 운이다.
대신 분할의 효과를 **타이밍 오차**로 잰다.

  타이밍 오차 = |실제 평균 매수 단가 / 그 주 평균 종가 − 1|
  보상       = −(타이밍 오차 + 회차당 부담 × (회차 수 − 1))

한 번에 사면 그 날 가격에 운이 몰리고(타이밍 오차↑), 많이 나누면 오차는 줄지만
회차마다 수수료·번거로움이 든다. 등급(변동성)별로 이 균형이 가장 좋은 회차 수를
과거 데이터(walk-forward 등급) + 사용자 매수 로그로 고르는 것이 '분할 규칙 학습'이다.
상태 = 등급, 행동 = 회차 수, 보상 = 위 식인 한 스텝 강화학습(contextual bandit)이며,
과거 주마다 모든 행동의 결과를 계산할 수 있어 오프라인으로 학습·검증한다.

    python -m gold_service.policy show
    python -m gold_service.policy train [--feedback data/feedback/feedback.csv] [--cost 0.001] [--apply]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from gold_service.grading import Grade, grade_series
from gold_service.planner import SPLIT_RULES

log = logging.getLogger("gold_service")

# 행동: 회차 수 → 매수 요일 (0=월). 기본 규칙의 요일 패턴과 같다.
ACTIONS: dict[int, list[int]] = {1: [0], 2: [0, 3], 3: [0, 2, 4], 5: [0, 1, 2, 3, 4]}
GRADE_ORDER = [Grade.LOW, Grade.NORMAL, Grade.HIGH, Grade.VERY_HIGH]
DEFAULT_COST = 0.001  # 회차가 1번 늘 때마다 매수액의 0.1%만큼 부담으로 본다
HOLDOUT_WEEKS = 52
MIN_WEEK_DAYS = 3
TRAIN_START = "2017-06-01"


# ---------------------------------------------------------------- 규칙 표현
def rule_to_json(rule: dict[Grade, list[int]]) -> dict[str, list[int]]:
    return {g.value: list(rule[g]) for g in GRADE_ORDER}


def rule_from_json(data: dict) -> dict[Grade, list[int]]:
    rule = {Grade(k): list(v) for k, v in data.items()}
    validate_rule(rule)
    return rule


def validate_rule(rule: dict[Grade, list[int]]) -> None:
    if set(rule) != set(GRADE_ORDER):
        raise ValueError("모든 등급의 규칙이 필요합니다")
    allowed = {tuple(p) for p in ACTIONS.values()}
    for grade, days in rule.items():
        if tuple(days) not in allowed:
            raise ValueError(f"{grade.label}: 허용되지 않은 요일 패턴 {days}")


def is_monotonic(rule: dict[Grade, list[int]]) -> bool:
    """변동성이 클수록 회차가 같거나 많아야 한다 (상식 검사)."""
    counts = [len(rule[g]) for g in GRADE_ORDER]
    return all(a <= b for a, b in zip(counts, counts[1:]))


def policy_version(rule: dict[Grade, list[int]], cost: float) -> str:
    key = json.dumps({"rule": rule_to_json(rule), "cost": cost}, sort_keys=True)
    return "policy-" + hashlib.sha1(key.encode()).hexdigest()[:8]


DEFAULT_RULE: dict[Grade, list[int]] = {g: list(SPLIT_RULES[g]) for g in GRADE_ORDER}


# ---------------------------------------------------------------- 시뮬레이션 데이터
def _plan_days(days: list[pd.Timestamp], pattern: list[int]) -> list[pd.Timestamp]:
    """planner.resolve_trade_dates 와 같은 규칙: 휴장이면 그 주 다음 거래일, 없으면 마지막 거래일."""
    return [next((d for d in days if d.weekday() >= wd), days[-1]) for wd in pattern]


def equal_amount_avg_cost(prices: list[float], amounts: list[float] | None = None) -> float:
    """금액을 나눠 샀을 때 평균 단가 = 총액 / 총수량."""
    amounts = amounts or [1.0] * len(prices)
    return sum(amounts) / sum(a / p for a, p in zip(amounts, prices))


def weekly_samples(close: pd.Series, grades: pd.Series) -> pd.DataFrame:
    """주마다 모든 행동(1·2·3·5회)의 결과를 계산한다.

    close: DatetimeIndex 종가. grades: 날짜별 등급(Grade 또는 None), 그 날 종가 기준.
    주의 등급은 그 주 첫 거래일 **전** 마지막 등급 (플랜을 만드는 시점과 같음).
    """
    grades = grades.dropna()
    rows = []
    for _, week in close.groupby(close.index.to_period("W-SUN")):
        if len(week) < MIN_WEEK_DAYS:
            continue
        before = grades.index[grades.index < week.index[0]]
        if len(before) == 0:
            continue
        grade = grades.loc[before[-1]]
        days = list(week.index)
        week_mean = float(week.mean())
        for n, pattern in ACTIONS.items():
            avg = equal_amount_avg_cost([float(week[d]) for d in _plan_days(days, pattern)])
            rows.append({"week_start": days[0].date(), "grade": Grade(grade).value, "n": n, "avg_cost": avg,
                         "week_mean": week_mean, "timing_error": abs(avg / week_mean - 1), "source": "history"})
    return pd.DataFrame(rows, columns=["week_start", "grade", "n", "avg_cost", "week_mean", "timing_error", "source"])


def history_samples(close: pd.Series, start: str = TRAIN_START) -> pd.DataFrame:
    """walk-forward 예측으로 과거 등급을 만든 뒤 주별 샘플을 만든다 (미래 정보 없음)."""
    from gold_service.models import walk_forward

    wf = walk_forward(close, start)
    grades = grade_series(wf["sigma"])["grade"]
    return weekly_samples(close, grades)


def log_samples(feedback_csv: Path, close: pd.Series) -> tuple[pd.DataFrame, dict]:
    """사용자 매수 로그(feedback.csv)를 같은 형식의 샘플로 바꾼다.

    모든 회차를 기록했고, 그 주 종가가 3일 이상 있는 접수만 쓴다 (주 평균가가 필요).
    """
    stats = {"rows": 0, "used": 0, "incomplete": 0, "no_week_prices": 0}
    rows = []
    with feedback_csv.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            stats["rows"] += 1
            try:
                n = int(r["n_splits"])
                done = int(r.get("trades_done") or 0)
                grade = next(g for g in GRADE_ORDER if r["grade"] in (g.value, g.label))
            except (KeyError, ValueError, StopIteration):
                stats["incomplete"] += 1
                continue
            if n not in ACTIONS or done < n or not r.get("exec_avg_cost") or not r.get("exec_first_date"):
                stats["incomplete"] += 1
                continue
            first = pd.Timestamp(r["exec_first_date"])
            week = close[close.index.to_period("W-SUN") == first.to_period("W-SUN")]
            if len(week) < MIN_WEEK_DAYS:
                stats["no_week_prices"] += 1
                continue
            avg, mean = float(r["exec_avg_cost"]), float(week.mean())
            rows.append({"week_start": week.index[0].date(), "grade": grade.value, "n": n, "avg_cost": avg,
                         "week_mean": mean, "timing_error": abs(avg / mean - 1), "source": "log"})
            stats["used"] += 1
    return pd.DataFrame(rows, columns=["week_start", "grade", "n", "avg_cost", "week_mean", "timing_error", "source"]), stats


# ---------------------------------------------------------------- 평가·학습
def reward(timing_error, n, cost: float):
    return -(timing_error + cost * (n - 1))


def evaluate_rule(samples: pd.DataFrame, rule: dict[Grade, list[int]], cost: float) -> dict:
    """규칙대로 샀을 때 vs 월요일 한 번에(1회) vs 매일(5회)의 주별 결과 요약."""
    hist = samples[samples["source"] == "history"]
    if hist.empty:
        return {"weeks": 0}
    wide = hist.pivot_table(index=["week_start", "grade"], columns="n", values=["timing_error", "avg_cost"])
    wide = wide.reset_index()
    chosen_n = wide["grade"].map(lambda g: len(rule[Grade(g)]))
    err = np.array([wide[("timing_error", n)].iloc[i] for i, n in enumerate(chosen_n)])
    cost_avg = np.array([wide[("avg_cost", n)].iloc[i] for i, n in enumerate(chosen_n)])
    lump_err, daily_err = wide[("timing_error", 1)].to_numpy(), wide[("timing_error", 5)].to_numpy()
    by_grade = {}
    for g in GRADE_ORDER:
        mask = (wide["grade"] == g.value).to_numpy()
        if mask.any():
            by_grade[g.label] = {
                "weeks": int(mask.sum()), "n_splits": len(rule[g]),
                "timing_error": round(float(err[mask].mean()), 6),
                "lump_timing_error": round(float(lump_err[mask].mean()), 6),
            }
    return {
        "weeks": int(len(wide)),
        "period_start": str(wide["week_start"].min()),
        "period_end": str(wide["week_start"].max()),
        "cost_per_trade": cost,
        "avg_trades": round(float(chosen_n.mean()), 3),
        "timing_error": round(float(err.mean()), 6),
        "timing_error_worst": round(float(err.max()), 6),
        "lump_timing_error": round(float(lump_err.mean()), 6),
        "lump_timing_error_worst": round(float(lump_err.max()), 6),
        "daily_timing_error": round(float(daily_err.mean()), 6),
        "cheaper_than_lump_share": round(float((cost_avg < wide[("avg_cost", 1)].to_numpy()).mean()), 4),
        "reward": round(float(reward(err, chosen_n.to_numpy(), cost).mean()), 6),
        "by_grade": by_grade,
    }


def mean_reward(samples: pd.DataFrame, rule: dict[Grade, list[int]], cost: float) -> float | None:
    picked = samples[samples.apply(lambda r: r["n"] == len(rule[Grade(r["grade"])]), axis=1)] if len(samples) else samples
    if picked.empty:
        return None
    return float(reward(picked["timing_error"], picked["n"], cost).mean())


def fit_rule(samples: pd.DataFrame, cost: float, fallback: dict[Grade, list[int]]) -> dict[Grade, list[int]]:
    """등급별로 평균 보상이 가장 큰 회차 수를 고른다 (동점이면 회차가 적은 쪽)."""
    rule = {}
    for g in GRADE_ORDER:
        part = samples[samples["grade"] == g.value]
        if part.empty:
            rule[g] = list(fallback[g])
            continue
        scores = part.assign(r=reward(part["timing_error"], part["n"], cost)).groupby("n")["r"].mean()
        best = max(scores.index, key=lambda n: (round(scores[n], 12), -n))
        rule[g] = list(ACTIONS[int(best)])
    return rule


@dataclass
class TrainResult:
    candidate: dict[Grade, list[int]]
    accepted: bool
    reason: str
    report: dict


def train(samples: pd.DataFrame, current: dict[Grade, list[int]], cost: float,
          holdout_weeks: int = HOLDOUT_WEEKS) -> TrainResult:
    """최근 holdout_weeks 주를 검증용으로 떼고, 그 전 데이터(+로그)로 학습한다.

    채택 조건: 등급이 높을수록 회차가 같거나 많고, 검증 기간 평균 보상이 현재 규칙보다 높을 것.
    """
    weeks = sorted(samples.loc[samples["source"] == "history", "week_start"].unique())
    if len(weeks) <= holdout_weeks + 52:
        raise ValueError(f"학습할 과거 주가 부족합니다 ({len(weeks)}주)")
    cutoff = weeks[-holdout_weeks]
    train_part = samples[(samples["week_start"] < cutoff) | (samples["source"] == "log")]
    holdout = samples[(samples["week_start"] >= cutoff) & (samples["source"] == "history")]
    candidate = fit_rule(train_part, cost, current)

    cur_score, new_score = mean_reward(holdout, current, cost), mean_reward(holdout, candidate, cost)
    if rule_to_json(candidate) == rule_to_json(current):
        accepted, reason = False, "학습 결과가 현재 규칙과 같습니다"
    elif not is_monotonic(candidate):
        accepted, reason = False, "변동성이 클수록 회차가 같거나 많아야 하는 조건을 어겨 채택하지 않습니다"
    elif new_score is None or cur_score is None or new_score <= cur_score:
        accepted, reason = False, "검증 기간 보상이 현재 규칙보다 낫지 않아 채택하지 않습니다"
    else:
        accepted, reason = True, "검증 기간 보상이 현재 규칙보다 높아 채택합니다"

    report = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cost_per_trade": cost,
        "train_weeks": int(train_part.loc[train_part["source"] == "history", "week_start"].nunique()),
        "log_samples": int((train_part["source"] == "log").sum()),
        "holdout_weeks": int(holdout["week_start"].nunique()),
        "holdout_start": str(cutoff),
        "holdout_reward_current": None if cur_score is None else round(cur_score, 6),
        "holdout_reward_candidate": None if new_score is None else round(new_score, 6),
        "current_rule": rule_to_json(current),
        "candidate_rule": rule_to_json(candidate),
        "accepted": accepted,
        "reason": reason,
    }
    return TrainResult(candidate, accepted, reason, report)


# ---------------------------------------------------------------- DB 연동
def active_rule(session) -> tuple[dict[Grade, list[int]], str | None]:
    """서비스에 쓰는 규칙과 버전. DB에 없으면 기본 규칙(버전 None)."""
    from gold_service import db

    row = db.active_policy_row(session)
    if row is None:
        return dict(DEFAULT_RULE), None
    return rule_from_json(row.rule), row.version


def ensure_active_policy(session, close: pd.Series, cost: float = DEFAULT_COST) -> str:
    """활성 규칙이 없으면 기본 규칙을 시뮬레이션 결과와 함께 등록한다."""
    from gold_service import db

    row = db.active_policy_row(session)
    if row is not None:
        return row.version
    samples = history_samples(close)
    version = policy_version(DEFAULT_RULE, cost)
    metrics = {"simulation": evaluate_rule(samples, DEFAULT_RULE, cost), "training": None}
    db.save_policy(session, version, "default", rule_to_json(DEFAULT_RULE), cost, metrics, activate=True)
    log.info("기본 분할 규칙 등록: %s", version)
    return version


def _load_close(session, settings) -> pd.Series:
    from gold_service import db
    from gold_service.sources import build_source

    close = db.load_close(session, date.max)
    if len(close) < 600:
        prices = build_source(settings).fetch(None, date.max)
        close = pd.Series(prices["close"].values, index=pd.DatetimeIndex(pd.to_datetime(prices["date"])), name="close")
    return close


def format_rule(rule_json: dict) -> str:
    names = ["월", "화", "수", "목", "금"]
    return ", ".join(f"{Grade(k).label} {len(v)}회({'·'.join(names[d] for d in v)})" for k, v in rule_json.items())


def main(argv: list[str] | None = None) -> int:
    from sqlalchemy.orm import Session

    from gold_service import db
    from gold_service.config import Settings

    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("gold_service.models").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="분할 규칙 시뮬레이션·학습")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="현재 서비스 중인 규칙과 이력")
    tr = sub.add_parser("train", help="과거 데이터 + 매수 로그로 규칙 학습")
    tr.add_argument("--feedback", type=Path, help="gold_service.feedback 이 만든 feedback.csv")
    tr.add_argument("--cost", type=float, default=DEFAULT_COST, help="회차당 부담 (기본 0.001 = 0.1%%)")
    tr.add_argument("--holdout-weeks", type=int, default=HOLDOUT_WEEKS)
    tr.add_argument("--apply", action="store_true", help="채택 조건을 통과하면 서비스 규칙으로 등록")
    tr.add_argument("--force", action="store_true", help="채택 조건과 무관하게 등록 (시연용, 비추천)")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    engine = db.make_engine(settings.database_url)
    db.init_db(engine)
    try:
        with Session(engine) as session, session.begin():
            if args.cmd == "show":
                for row in db.policy_rows(session):
                    mark = "▶" if row.active else " "
                    sim = row.metrics.get("simulation") or {}
                    print(f"{mark} {row.version} [{row.source}] {row.created_at:%Y-%m-%d %H:%M} · {format_rule(row.rule)}"
                          f" · 타이밍 오차 {sim.get('timing_error', float('nan')) * 100:.3f}%")
                if not db.policy_rows(session):
                    print("등록된 규칙이 없습니다 (run_daily 또는 policy train --apply 실행 시 등록)")
                return 0

            close = _load_close(session, settings)
            ensure_active_policy(session, close, args.cost)
            current, current_version = active_rule(session)
            samples = history_samples(close)
            log_stats = None
            if args.feedback:
                logs, log_stats = log_samples(args.feedback, close)
                samples = pd.concat([samples, logs], ignore_index=True)
            result = train(samples, current, args.cost, args.holdout_weeks)
            result.report["log_stats"] = log_stats
            result.report["previous_version"] = current_version

            print(f"현재 규칙  ({current_version}): {format_rule(rule_to_json(current))}")
            print(f"학습 규칙             : {format_rule(rule_to_json(result.candidate))}")
            print(f"검증 {result.report['holdout_weeks']}주 평균 보상: 현재 {result.report['holdout_reward_current']}"
                  f" → 학습 {result.report['holdout_reward_candidate']}")
            print(f"로그 샘플: {result.report['log_samples']}건 {log_stats or ''}")
            print(f"판정: {result.reason}")

            if args.apply and (result.accepted or args.force):
                version = policy_version(result.candidate, args.cost)
                metrics = {"simulation": evaluate_rule(samples, result.candidate, args.cost), "training": result.report}
                db.save_policy(session, version, "trained", rule_to_json(result.candidate), args.cost, metrics,
                               activate=True)
                print(f"서비스 규칙으로 등록: {version}")
            elif args.apply:
                print("채택 조건을 통과하지 못해 기존 규칙을 유지합니다.")
    except Exception:
        log.exception("분할 규칙 학습 실패")
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
