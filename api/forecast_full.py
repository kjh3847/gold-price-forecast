from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.storage import get_session
from gold_service.export_json import build_payload

router = APIRouter()


@router.get("/api/forecast/full")
def get_full_forecast(session: Session = Depends(get_session)):
    try:
        return build_payload(session)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
