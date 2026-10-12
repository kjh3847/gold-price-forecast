"""웹(React)이 읽을 forecast.json 내보내기.

    python -m gold_service.export_json --out web/public/data/forecast.json [--date YYYY-MM-DD]

DB(forecasts, prices, evaluations)만 읽는다. run_daily → (evaluate) → export_json 순서로 실행한다.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from gold_service import db
from gold_service.bands import COVERAGE
from gold_service.config import Settings
from gold_service.features import HORIZON
from gold_service.grading import Grade
from gold_service.planner import SPLIT_RULES

log = logging.getLogger("gold_service")

HISTORY_DAYS = 260
CURRENCY, UNIT = "USD", "oz"


def _num(x, ndigits: int) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
        return None
    return round(float(x), ndigits)


def _label(code) -> str | None:
    return None if code is None or pd.isna(code) else Grade(code).label


def split_rule_json() -> dict[str, list[int]]:
    return {grade.label: list(days) for grade, days in SPLIT_RULES.items()}


def build_payload(session: Session, as_of: date | None = None) -> dict:
    end = as_of or date.max
    forecasts = db.load_forecasts(session, end)
    if forecasts.empty:
        raise ValueError("forecasts가 비어 있습니다. 먼저 run_daily를 실행하세요")
    close = db.load_close(session, end)
    df = forecasts.join(close, how="left")
    last = df.iloc[-1]
    as_of_date = df.index[-1].date()
    if pd.isna(last["band_low"]):
        raise ValueError(f"{as_of_date} 가격 범위가 없습니다. run_daily를 다시 실행하세요")

    history = [
        {
            "date": d.date().isoformat(),
            "price": _num(row["close"], 2),
            "sigma_daily": _num(row["sigma"], 6),
            "grade": _label(row["grade"]),
            "band_low": _num(row["band_low"], 2),
            "band_high": _num(row["band_high"], 2),
        }
        for d, row in df.tail(HISTORY_DAYS).iterrows()
    ]
    evaluation = db.latest_evaluation(session)
    if evaluation is None:
        log.warning("평가 결과가 없습니다 (python -m gold_service.evaluate --start 2024-01-01). evaluation=null로 내보냅니다")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of_date.isoformat(),
        "currency": CURRENCY,
        "unit": UNIT,
        "price": _num(last["close"], 2),
        "sigma_daily": _num(last["sigma"], 6),
        "grade": _label(last["grade"]),
        "percentile": _num(None if pd.isna(last["percentile"]) else last["percentile"] / 100, 4),
        "is_fallback": bool(last["is_fallback"]),
        "band": {
            "horizon_days": HORIZON,
            "coverage": COVERAGE,
            "z": _num(last["z"], 4),
            "z_is_default": bool(last["z_is_default"]),
            "low": _num(last["band_low"], 2),
            "high": _num(last["band_high"], 2),
        },
        "history": history,
        "evaluation": evaluation,
        "split_rule": split_rule_json(),
    }


def write_json(payload: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="forecast.json 내보내기")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--date", type=date.fromisoformat, default=None, help="기준일 (기본: DB의 마지막 예측일)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        engine = db.make_engine(settings.database_url)
        db.init_db(engine)
        with Session(engine) as session:
            payload = build_payload(session, args.date)
        write_json(payload, args.out)
    except Exception:
        log.exception("JSON 내보내기 실패")
        return 1
    log.info("내보냄: %s (기준일 %s, history %d일)", args.out, payload["as_of"], len(payload["history"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
