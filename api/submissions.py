import math
from datetime import date, datetime, timedelta, timezone
from typing import Literal
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


def now():
    return datetime.now(timezone.utc).isoformat()


def response(row):
    return {key: getattr(row, key) for key in ("id", "created_at", "user_input", "forecast", "actual", "actual_at")}


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
