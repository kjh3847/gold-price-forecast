"""Python planner 결과를 React 테스트용 픽스처로 내보낸다.

    python -m gold_service.export_planner_fixtures --out web/src/planner.fixtures.json

등급 4개 × 주간 금액 3개 × (휴장 없는 주 / 휴장 있는 주) 케이스.
React의 planner.ts가 이 파일과 똑같은 결과를 내는지 Vitest로 확인한다.
요일은 0=월 … 4=금.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from gold_service.export_json import split_rule_json
from gold_service.grading import Grade
from gold_service.planner import build_plan

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "web" / "src" / "planner.fixtures.json"
MONDAY = date(2026, 10, 5)  # 기준 주 (요일만 의미 있음)
AMOUNTS = [300_000, 100_000, 99_999]
WEEKS = {
    "휴장 없음": [0, 1, 2, 3, 4],
    "월·목 휴장": [1, 2, 4],
    "금 휴장": [0, 1, 2, 3],
}


def build_fixtures() -> dict:
    cases = []
    for grade in Grade:
        for amount in AMOUNTS:
            for week_name, weekdays in WEEKS.items():
                plan = build_plan(
                    grade=grade,
                    sigma=0.01,
                    forecast_date=MONDAY - timedelta(days=3),
                    weekly_amount=amount,
                    trading_days=[MONDAY + timedelta(days=w) for w in weekdays],
                )
                cases.append(
                    {
                        "name": f"{grade.label} / {amount:,}원 / {week_name}",
                        "grade": grade.label,
                        "weekly_amount": amount,
                        "trading_weekdays": weekdays,
                        "expected": [
                            {
                                "seq": it.seq,
                                "planned_weekday": it.planned_weekday,
                                "trade_weekday": it.trade_date.weekday(),
                                "amount": it.amount,
                            }
                            for it in plan.items
                        ],
                    }
                )
    return {"split_rule": split_rule_json(), "cases": cases}


def dumps(fixtures: dict) -> str:
    return json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="planner 픽스처 내보내기")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dumps(build_fixtures()), encoding="utf-8")
    print(f"내보냄: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
