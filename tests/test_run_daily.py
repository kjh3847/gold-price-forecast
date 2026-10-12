"""run_daily 통합 테스트 (SQLite): 멱등성, 플랜 생성, 대체값 저장, 종료 코드."""
from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gold_service import db, models, run_daily
from gold_service.config import Settings

from .conftest import DATA_CSV

MONDAY = date(2026, 9, 21)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    s = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        price_source="csv",
        price_csv_path=DATA_CSV,
        price_csv_date_col="date",
        price_csv_close_col="gold",
        holidays_file=None,
        backfill_days=150,
        log_level="INFO",
    )
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: s))
    engine = db.make_engine(s.database_url)
    db.init_db(engine)
    with Session(engine) as session, session.begin():
        db.add_user(session, "테스트", 300_000)
    return s


def counts(settings):
    with Session(db.make_engine(settings.database_url)) as session:
        return {
            t.__tablename__: session.scalar(select(func.count()).select_from(t))
            for t in (db.Price, db.ModelParamsRow, db.ForecastRow, db.BuyPlan, db.PlanItemRow, db.MonitoringRow)
        }


def test_rerun_is_idempotent_and_creates_plan(settings):
    first = run_daily.run(MONDAY, settings)
    before = counts(settings)
    second = run_daily.run(MONDAY, settings)
    assert counts(settings) == before
    assert first.sigma == second.sigma and first.grade == second.grade

    assert first.plans_written == 1
    assert before["buy_plans"] == 1 and before["monitoring"] == 1
    assert before["forecasts"] == 150

    with Session(db.make_engine(settings.database_url)) as session:
        plan = session.scalar(select(db.BuyPlan))
        assert plan.week_start == MONDAY
        assert plan.forecast_date == date(2026, 9, 18)  # 직전 거래일(금) 예측 사용
        assert sum(i.amount for i in plan.items) == 300_000


def test_mid_week_run_does_not_create_plan(settings):
    run_daily.run(MONDAY, settings)
    result = run_daily.run(date(2026, 9, 22), settings)
    assert result.forecasts_written == 1
    assert result.plans_written == 0 and result.monitoring is None


def test_model_failure_is_stored_as_fallback(settings, monkeypatch):
    monkeypatch.setattr(models, "predict", lambda *a: (_ for _ in ()).throw(RuntimeError("장애")))
    result = run_daily.run(MONDAY, settings)
    assert result.is_fallback
    with Session(db.make_engine(settings.database_url)) as session:
        row = session.get(db.ForecastRow, MONDAY)
        assert row.is_fallback and row.sigma == pytest.approx(row.rv22)


def test_exit_codes(settings, monkeypatch):
    assert run_daily.main(["--date", "2026-09-26"]) == 0  # 토요일
    assert run_daily.main(["--date", "2026-09-29"]) == 3  # 거래일인데 데이터 없음
    assert run_daily.main(["--date", "not-a-date"]) == 2
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: replace(settings, price_csv_path=DATA_CSV.with_name("x.csv"))))
    assert run_daily.main(["--date", "2026-09-21"]) == 1


def test_band_is_saved(settings):
    run_daily.run(MONDAY, settings)
    with Session(db.make_engine(settings.database_url)) as session:
        rows = session.scalars(select(db.ForecastRow).order_by(db.ForecastRow.date)).all()
        assert all(r.band_low < r.band_high for r in rows)
        # 오차 표본 120개는 백필 125번째 날부터 쌓인다 (i ≤ t−5)
        assert all(r.z_is_default for r in rows[:124]) and not any(r.z_is_default for r in rows[124:])
        assert rows[-1].date == MONDAY


def test_init_db_adds_columns_to_old_db(tmp_path):
    from sqlalchemy import inspect, text

    engine = db.make_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # z·band 컬럼이 없던 예전 스키마
        conn.execute(text("CREATE TABLE forecasts (date DATE PRIMARY KEY, sigma FLOAT NOT NULL, is_fallback BOOLEAN NOT NULL)"))
    db.init_db(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("forecasts")}
    assert {"z", "band_low", "band_high", "z_is_default"} <= cols
