"""forecast.json 스키마, 커밋된 샘플·플랜 픽스처가 최신인지."""
import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from gold_service import db, export_json, run_daily
from gold_service.export_planner_fixtures import DEFAULT_OUT, build_fixtures, dumps

from .test_run_daily import settings  # noqa: F401 - fixture 재사용

WEB = Path(__file__).resolve().parent.parent / "web"
TOP_KEYS = {"generated_at", "as_of", "currency", "unit", "price", "sigma_daily", "grade", "percentile",
            "is_fallback", "band", "history", "evaluation", "split_rule"}
HISTORY_KEYS = {"date", "price", "sigma_daily", "grade", "band_low", "band_high"}
GRADES = {"낮음", "보통", "높음", "매우 높음"}


def check_schema(p: dict):
    assert TOP_KEYS <= p.keys()
    assert (p["currency"], p["unit"]) == ("USD", "oz")
    assert p["grade"] in GRADES
    assert 0 <= p["percentile"] <= 1
    assert p["band"]["horizon_days"] == 5 and p["band"]["coverage"] == 0.9
    assert p["band"]["low"] < p["price"] < p["band"]["high"]
    assert all(HISTORY_KEYS <= h.keys() for h in p["history"])
    assert p["history"][-1]["date"] == p["as_of"]
    assert p["split_rule"] == {"낮음": [0], "보통": [0, 3], "높음": [0, 2, 4], "매우 높음": [0, 1, 2, 3, 4]}


def test_export_from_db(settings):  # noqa: F811
    run_daily.run(date(2026, 9, 24), settings)
    with Session(db.make_engine(settings.database_url)) as session:
        payload = export_json.build_payload(session)
    check_schema(payload)
    assert payload["as_of"] == "2026-09-24"
    assert len(payload["history"]) == 150  # backfill_days 만큼만 있음
    assert payload["evaluation"] is None
    json.dumps(payload)  # NaN 없이 직렬화 가능


@pytest.mark.parametrize("name", ["forecast.sample.json", "forecast.json"])
def test_committed_json_follows_schema(name):
    payload = json.loads((WEB / "public" / "data" / name).read_text(encoding="utf-8"))
    check_schema(payload)
    assert len(payload["history"]) == export_json.HISTORY_DAYS
    assert {"hit_rate", "avg_width", "hit_rate_nonoverlap", "baseline", "period_start", "period_end"} <= payload["evaluation"].keys()


def test_planner_fixtures_are_up_to_date():
    """규칙을 바꿨다면 python -m gold_service.export_planner_fixtures 로 다시 내보내야 한다."""
    assert DEFAULT_OUT.read_text(encoding="utf-8") == dumps(build_fixtures())
    assert len(build_fixtures()["cases"]) == 4 * 3 * 3
