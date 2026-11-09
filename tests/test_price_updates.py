from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.health import app
from gold_service import db, price_updates, run_daily
from gold_service.trading_calendar import TradingCalendar
from .test_run_daily import settings  # noqa: F401

CSV = """date,close_usd_per_troy_oz
2026-09-25,4284.97
2026-09-26,4284.97
2026-09-28,4300
2026-09-29,4250
2026-09-30,4260
2026-10-01,4270
# Source: GoldPrice.com
"""
NOW = datetime(2026, 10, 2, 15, tzinfo=timezone.utc)


@pytest.fixture
def api(settings, monkeypatch):
    run_daily.run(date(2026, 9, 24), settings)
    monkeypatch.setattr(price_updates, "last_completed_day", lambda calendar, now=None: date(2026, 10, 1))
    return TestClient(app)


def test_cutoff_and_threshold(settings):
    calendar = TradingCalendar()
    # Monday in NY uses the last Friday; excludes current day's unfinished close.
    assert price_updates.last_completed_day(calendar, datetime(2026, 11, 2, 15, tzinfo=timezone.utc)) == date(2026, 10, 30)
    engine = db.make_engine(settings.database_url)
    with Session(engine) as session:
        session.add(db.Price(date=date(2026, 9, 24), close=4273.8, source="test"))
        session.flush()
        four = price_updates.status(session, settings, datetime(2026, 10, 1, 15, tzinfo=timezone.utc))
        five = price_updates.status(session, settings, NOW)
        assert four["missing_count"] == 4 and not four["needs_upload"]
        assert five["missing_count"] == 5 and five["needs_upload"]
        assert (five["required_from"], five["required_to"]) == (date(2026, 9, 25), date(2026, 10, 1))
    engine.dispose()


def test_upload_real_model_and_db(api, settings):
    engine = db.make_engine(settings.database_url)
    with Session(engine) as session:
        params_before = session.scalar(select(func.count()).select_from(db.ModelParamsRow))
    status = api.get("/api/prices/status").json()
    assert status["needs_upload"] and status["missing_count"] == 5
    response = api.post("/api/prices/import", json={"csv_text": CSV})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["added_count"] == 5 and result["skipped_nontrading_rows"] == 1
    assert result["retrained_dates"] == []  # no forced retraining before 63-day interval
    assert not result["data_status"]["needs_upload"]
    forecast = result["forecast"]
    assert forecast["as_of"] == "2026-10-01"
    assert forecast["sigma_daily"] > 0 and not forecast["is_fallback"]
    points = forecast["volatility_projection"]
    assert [p["date"] for p in points] == ["2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]
    assert points[-1]["cumulative_sigma_pct"] == pytest.approx(points[0]["cumulative_sigma_pct"] * 5 ** .5, abs=.0002)
    assert api.get("/api/forecast/full").json()["as_of"] == "2026-10-01"
    with Session(engine) as session:
        assert session.get(db.Price, date(2026, 10, 1)).close == 4270
        assert session.get(db.Price, date(2026, 9, 26)) is None
        assert session.scalar(select(func.count()).select_from(db.ModelParamsRow)) == params_before
    # Running the CSV-backed batch again preserves uploaded newer prices/forecasts.
    run_daily.run(date(2026, 9, 24), settings)
    assert api.get("/api/forecast/latest").json()["date"] == "2026-10-01"
    assert api.post("/api/prices/import", json={"csv_text": CSV}).status_code == 422
    engine.dispose()


@pytest.mark.parametrize("text", [
    CSV.replace("2026-09-29,4250\n", ""),
    CSV + "2026-09-24,1\n",
    CSV + "2026-10-01,99\n",
    CSV.replace("4250", "nan"),
    CSV.replace("4250", "-1"),
    CSV.replace("date,close_usd_per_troy_oz", "date,wrong"),
    CSV + "2026-10-02,4300\n",
])
def test_bad_upload_is_atomic(api, settings, text):
    response = api.post("/api/prices/import", json={"csv_text": text})
    assert response.status_code == 422, response.text
    assert api.get("/api/prices/status").json()["last_price_date"] == "2026-09-24"
    assert api.get("/api/forecast/latest").json()["date"] == "2026-09-24"


def test_model_pipeline_error_rolls_back(api, monkeypatch):
    def fail(*args):
        raise RuntimeError("pipeline failure")
    monkeypatch.setattr(price_updates, "bands", fail)
    response = api.post("/api/prices/import", json={"csv_text": CSV})
    assert response.status_code == 500
    assert api.get("/api/prices/status").json()["last_price_date"] == "2026-09-24"
    assert api.get("/api/forecast/latest").json()["date"] == "2026-09-24"


def test_holiday_and_bom_parser():
    calendar = TradingCalendar({date(2026, 9, 28)})
    prices, skipped = price_updates.parse_csv('\ufeff' + CSV, calendar, date(2026, 10, 1))
    assert skipped == 2 and date(2026, 9, 28) not in prices
