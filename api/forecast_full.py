from fastapi import APIRouter
from sqlalchemy.orm import Session

from gold_service import db
from gold_service.config import Settings
from gold_service.export_json import build_payload

router = APIRouter()

@router.get("/api/forecast/full")
def get_full_forecast():
    settings = Settings.from_env()
    engine = db.make_engine(settings.database_url)

    try:
        with Session(engine) as session:
            payload = build_payload(session)
            return payload
    finally:
        engine.dispose()