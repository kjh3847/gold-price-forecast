import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.storage import get_session
from gold_service.config import Settings
from gold_service.price_updates import import_prices, status

router = APIRouter()


class CSVInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(min_length=1, max_length=2_000_000)


@router.get("/api/prices/status")
def price_status(session: Session = Depends(get_session)):
    return status(session, Settings.from_env())


@router.post("/api/prices/import")
def upload_prices(body: CSVInput, session: Session = Depends(get_session)):
    try:
        result = import_prices(session, body.csv_text, Settings.from_env())
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        session.rollback()
        logging.getLogger(__name__).exception("Price import/forecast failed")
        raise HTTPException(500, "가격 갱신 또는 예측에 실패했습니다. 이번 업로드는 저장되지 않았습니다.") from exc
