import math
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from sqlalchemy.orm import Session

from api.forecast_full import get_full_forecast
from api.storage import get_session
from gold_service import db
from gold_service.collection import deliver
from gold_service.trading_calendar import TradingCalendar
from gold_service.config import Settings
from gold_service.grading import Grade
from gold_service.planner import allocate_amounts, split_weekdays
from gold_service.policy import active_rule

KST = ZoneInfo("Asia/Seoul")
LABEL_TO_GRADE = {g.label: g for g in Grade}
TRADE_WINDOW_DAYS = 21

router = APIRouter()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    forecast_date: date
    weekly_amount: int = Field(strict=True, gt=0, le=1_000_000_000)
    product: Literal["금 현물", "금 ETF", "기타"]


class Actual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["boolean", "price"]
    value: StrictBool | float
    observed_on: date

    @model_validator(mode="before")
    @classmethod
    def validate_value(cls, values):
        if isinstance(values, dict):
            value = values.get("value")
            if values.get("kind") == "boolean" and type(value) is not bool:
                raise ValueError("T/F에는 boolean 값이 필요합니다")
            if values.get("kind") == "price" and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise ValueError("가격은 유한한 양수여야 합니다")
        return values


class Trade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trade_date: date
    price: float = Field(gt=0, allow_inf_nan=False)


def now():
    return datetime.now(timezone.utc).isoformat()


def trade_summary(row):
    plan = row.forecast.get("plan") or {}
    trades = row.executions
    total = sum(t.amount for t in trades)
    return {
        "n_splits": plan.get("n_splits"),
        "done": len(trades),
        "total_amount": total,
        # 금액을 나눠 샀을 때 평균 단가 = 총액 / Σ(회차 금액 / 단가)
        "avg_cost": round(total / sum(t.amount / t.price for t in trades), 4) if trades else None,
    }


def response(row):
    result = {key: getattr(row, key) for key in ("id", "created_at", "user_input", "forecast", "actual", "actual_at")}
    result["trades"] = [
        {"seq": t.seq, "trade_date": t.trade_date.isoformat(), "price": t.price, "amount": t.amount,
         "recorded_at": t.recorded_at}
        for t in row.executions
    ]
    result["trade_summary"] = trade_summary(row)
    return result


def plan_snapshot(session, grade_label, weekly_amount):
    """입력 시점의 서비스 분할 규칙으로 회차별 요일·금액을 고정해 둔다."""
    rule, version = active_rule(session)
    weekdays = split_weekdays(LABEL_TO_GRADE[grade_label], rule)
    amounts = allocate_amounts(weekly_amount, len(weekdays))
    return {
        "policy_version": version,
        "n_splits": len(weekdays),
        "items": [{"seq": i + 1, "weekday": wd, "amount": a} for i, (wd, a) in enumerate(zip(weekdays, amounts))],
    }


def record_event(session, row, kind):
    event = db.CollectionEvent(id=str(uuid4()), payload={"event_type": kind, "event_at": now(), **response(row)}, delivery={})
    session.add(event)
    session.commit()
    status = deliver(event)
    session.commit()
    return {**response(row), "delivery": status}


@router.post("/api/submissions", status_code=201)
def create_submission(body: Input, session: Session = Depends(get_session)):
    forecast = get_full_forecast(session)
    if body.forecast_date.isoformat() != forecast["as_of"]:
        raise HTTPException(409, "예측 기준일이 바뀌었습니다. 화면을 새로고침하세요.")
    snapshot = {k: v for k, v in forecast.items() if k not in ("history", "evaluation", "split_rule")}
    calendar = TradingCalendar.from_file(Settings.from_env().holidays_file)
    target = body.forecast_date
    for _ in range(snapshot["band"]["horizon_days"]):
        target += timedelta(days=1)
        while not calendar.is_trading_day(target):
            target += timedelta(days=1)
    snapshot["target_date"] = target.isoformat()
    snapshot["plan"] = plan_snapshot(session, snapshot["grade"], body.weekly_amount)
    row = db.Submission(id=str(uuid4()), created_at=now(), user_input=body.model_dump(mode="json"), forecast=snapshot)
    session.add(row)
    return record_event(session, row, "input_saved")


@router.get("/api/submissions/{receipt}")
def get_submission(receipt: UUID, session: Session = Depends(get_session)):
    row = session.get(db.Submission, str(receipt))
    if row is None:
        raise HTTPException(404, "접수번호를 찾을 수 없습니다.")
    return response(row)


@router.put("/api/submissions/{receipt}/actual")
def save_actual(receipt: UUID, body: Actual, session: Session = Depends(get_session)):
    row = session.get(db.Submission, str(receipt))
    if row is None:
        raise HTTPException(404, "접수번호를 찾을 수 없습니다.")
    target = date.fromisoformat(row.forecast["target_date"])
    if body.observed_on != target or target > datetime.now(timezone.utc).date():
        raise HTTPException(422, "실제 정답은 예측 대상일의 종가 기준으로 대상일 이후에 등록하세요.")
    actual = body.model_dump(mode="json")
    actual["within_band"] = (row.forecast["band"]["low"] <= body.value <= row.forecast["band"]["high"]) if body.kind == "price" else body.value
    row.actual, row.actual_at = actual, now()
    return record_event(session, row, "actual_saved")


@router.put("/api/submissions/{receipt}/trades/{seq}")
def save_trade(receipt: UUID, seq: int, body: Trade, session: Session = Depends(get_session)):
    """플랜 회차의 실제 매수(체결일·단가)를 기록한다. 같은 회차를 다시 보내면 덮어쓴다."""
    row = session.get(db.Submission, str(receipt))
    if row is None:
        raise HTTPException(404, "접수번호를 찾을 수 없습니다.")
    plan = row.forecast.get("plan")
    if not plan:
        raise HTTPException(409, "분할 플랜이 없는 예전 접수입니다. 새로 입력값을 저장하세요.")
    item = next((it for it in plan["items"] if it["seq"] == seq), None)
    if item is None:
        raise HTTPException(404, f"{seq}회차가 플랜에 없습니다.")
    as_of = date.fromisoformat(row.forecast["as_of"])
    today = datetime.now(KST).date()
    if not (as_of < body.trade_date <= min(today, as_of + timedelta(days=TRADE_WINDOW_DAYS))):
        raise HTTPException(422, f"체결일은 예측 기준일({as_of}) 이후 {TRADE_WINDOW_DAYS}일 이내이면서 오늘 이전이어야 합니다.")
    trade = next((t for t in row.executions if t.seq == seq), None)
    if trade is None:
        trade = db.Execution(seq=seq, amount=item["amount"])
        row.executions.append(trade)
    trade.trade_date, trade.price, trade.recorded_at = body.trade_date, body.price, now()
    session.flush()
    return record_event(session, row, "trade_saved")
