from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from api.storage import get_session
from gold_service import db

router = APIRouter()


@router.get("/api/forecast/latest")
def get_latest_forecast(session: Session = Depends(get_session)):
    row = session.scalar(select(db.ForecastRow).order_by(db.ForecastRow.date.desc()).limit(1))
    if row is None:
        raise HTTPException(404, "예측 데이터가 없습니다.")
    return {key: getattr(row, key) for key in ("date", "sigma", "grade", "band_low", "band_high")}
