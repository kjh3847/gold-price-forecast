"""DB 스키마와 저장소 함수 (SQLAlchemy 2.x, PostgreSQL/SQLite 공용).

모든 저장 함수는 자연키(date, (user_id, week_start) 등) 기준 upsert라서
같은 날짜로 다시 실행해도 행이 중복되지 않는다.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from gold_service.grading import Grade
from gold_service.models import Forecast, ModelParams
from gold_service.monitoring import MonitoringResult
from gold_service.planner import WeeklyPlan


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Price(Base):
    __tablename__ = "prices"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ModelParamsRow(Base):
    __tablename__ = "model_params"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trained_on: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    last_train_row: Mapped[date] = mapped_column(Date, nullable=False)
    n_train_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    har: Mapped[dict] = mapped_column(JSON, nullable=False)  # coef, intercept, resid_var
    garch: Mapped[dict] = mapped_column(JSON, nullable=False)  # mu, omega, alpha[1], beta[1], nu
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ForecastRow(Base):
    __tablename__ = "forecasts"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    sigma: Mapped[float] = mapped_column(Float, nullable=False)
    grade: Mapped[str | None] = mapped_column(String(16))
    percentile: Mapped[float | None] = mapped_column(Float)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    har_var: Mapped[float | None] = mapped_column(Float)
    garch_var: Mapped[float | None] = mapped_column(Float)
    rv22: Mapped[float | None] = mapped_column(Float)
    params_trained_on: Mapped[date | None] = mapped_column(Date)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    weekly_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 원
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BuyPlan(Base):
    __tablename__ = "buy_plans"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    grade: Mapped[str] = mapped_column(String(16), nullable=False)
    sigma: Mapped[float] = mapped_column(Float, nullable=False)
    range_5d: Mapped[float] = mapped_column(Float, nullable=False)
    weekly_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    items: Mapped[list["PlanItemRow"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanItemRow.seq"
    )


class PlanItemRow(Base):
    __tablename__ = "plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "seq"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("buy_plans.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=월
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False, default="MARKET")
    plan: Mapped[BuyPlan] = relationship(back_populates="items")


class Trade(Base):
    """실제 체결 기록 (스키마만, 기능 미구현)."""

    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("plan_items.id", ondelete="SET NULL"))
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MonitoringRow(Base):
    __tablename__ = "monitoring"
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    n_obs: Mapped[int] = mapped_column(Integer, nullable=False)
    hit_rate: Mapped[float | None] = mapped_column(Float)
    qlike_model: Mapped[float | None] = mapped_column(Float)
    qlike_baseline: Mapped[float | None] = mapped_column(Float)
    improvement: Mapped[float | None] = mapped_column(Float)
    alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------- 연결
def make_engine(url: str) -> Engine:
    return create_engine(url, future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------- prices
def upsert_prices(session: Session, df: pd.DataFrame, source: str) -> int:
    """가격을 upsert하고 새로 추가된 행 수를 돌려준다."""
    existing = {p.date: p for p in session.scalars(select(Price))}
    added = 0
    for row in df.itertuples(index=False):
        values = {k: (None if pd.isna(getattr(row, k)) else float(getattr(row, k))) for k in ("open", "high", "low", "close")}
        current = existing.get(row.date)
        if current is None:
            session.add(Price(date=row.date, source=source, **values))
            added += 1
        elif any(getattr(current, k) != v for k, v in values.items()):
            for k, v in values.items():
                setattr(current, k, v)
            current.source = source
    return added


def load_close(session: Session, end: date) -> pd.Series:
    rows = session.execute(select(Price.date, Price.close).where(Price.date <= end).order_by(Price.date)).all()
    s = pd.Series([r.close for r in rows], index=pd.DatetimeIndex([pd.Timestamp(r.date) for r in rows]), name="close")
    return s


# ---------------------------------------------------------------- model_params
def load_params(session: Session) -> list[ModelParams]:
    return [
        ModelParams.from_dict(
            {
                "trained_on": r.trained_on.isoformat(),
                "last_train_row": r.last_train_row.isoformat(),
                "n_train_rows": r.n_train_rows,
                "har": r.har,
                "garch": r.garch,
            }
        )
        for r in session.scalars(select(ModelParamsRow).order_by(ModelParamsRow.trained_on))
    ]


def save_params(session: Session, params: ModelParams) -> None:
    d = params.to_dict()
    row = session.scalar(select(ModelParamsRow).where(ModelParamsRow.trained_on == params.trained_on))
    if row is None:
        row = ModelParamsRow(trained_on=params.trained_on)
        session.add(row)
    row.last_train_row = params.last_train_row
    row.n_train_rows = params.n_train_rows
    row.har = d["har"]
    row.garch = d["garch"]


# ---------------------------------------------------------------- forecasts
def save_forecast(session: Session, fc: Forecast) -> None:
    row = session.get(ForecastRow, fc.date) or ForecastRow(date=fc.date)
    row.sigma = fc.sigma
    row.is_fallback = fc.is_fallback
    row.har_var = fc.har_var
    row.garch_var = fc.garch_var
    row.rv22 = fc.rv22
    row.params_trained_on = fc.params_trained_on
    row.error = fc.error
    session.add(row)


def save_grade(session: Session, d: date, percentile: float | None, grade: Grade | None) -> None:
    row = session.get(ForecastRow, d)
    row.percentile = percentile
    row.grade = grade.value if grade else None


def forecast_dates(session: Session, end: date) -> set[date]:
    return set(session.scalars(select(ForecastRow.date).where(ForecastRow.date <= end)))


def load_forecasts(session: Session, end: date) -> pd.DataFrame:
    rows = session.scalars(select(ForecastRow).where(ForecastRow.date <= end).order_by(ForecastRow.date)).all()
    df = pd.DataFrame(
        [
            {"date": pd.Timestamp(r.date), "sigma": r.sigma, "grade": r.grade, "percentile": r.percentile,
             "is_fallback": r.is_fallback, "rv22": r.rv22}
            for r in rows
        ],
        columns=["date", "sigma", "grade", "percentile", "is_fallback", "rv22"],
    )
    return df.set_index("date")


# ---------------------------------------------------------------- users / plans
def add_user(session: Session, name: str, weekly_amount: int) -> User:
    user = User(name=name, weekly_amount=weekly_amount, active=True)
    session.add(user)
    session.flush()
    return user


def active_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).where(User.active.is_(True)).order_by(User.id)))


def replace_plan(session: Session, user_id: int, plan: WeeklyPlan) -> BuyPlan:
    """(user_id, week_start) 플랜을 새 내용으로 교체한다."""
    old = session.scalar(select(BuyPlan).where(BuyPlan.user_id == user_id, BuyPlan.week_start == plan.week_start))
    if old is not None:
        session.delete(old)  # plan_items는 cascade로 함께 삭제
        session.flush()
    row = BuyPlan(
        user_id=user_id,
        week_start=plan.week_start,
        forecast_date=plan.forecast_date,
        grade=plan.grade.value,
        sigma=plan.sigma,
        range_5d=plan.range_5d,
        weekly_amount=plan.weekly_amount,
        items=[
            PlanItemRow(seq=it.seq, planned_weekday=it.planned_weekday, trade_date=it.trade_date,
                        amount=it.amount, order_type=it.order_type)
            for it in plan.items
        ],
    )
    session.add(row)
    session.flush()
    return row


# ---------------------------------------------------------------- monitoring
def save_monitoring(session: Session, m: MonitoringResult) -> None:
    row = session.get(MonitoringRow, m.date) or MonitoringRow(date=m.date)
    row.window_start = m.window_start
    row.window_end = m.window_end
    row.n_obs = m.n_obs
    row.hit_rate = m.hit_rate
    row.qlike_model = m.qlike_model
    row.qlike_baseline = m.qlike_baseline
    row.improvement = m.improvement
    row.alert = m.alert
    session.add(row)


def previous_improvements(session: Session, before: date) -> list[float | None]:
    return list(
        session.scalars(select(MonitoringRow.improvement).where(MonitoringRow.date < before).order_by(MonitoringRow.date))
    )
