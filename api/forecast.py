import sqlite3
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

DB_PATH = Path(__file__).resolve().parent.parent / "gold_service.db"

@router.get("/api/forecast/latest")
def get_latest_forecast():
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.row_factory = sqlite3.Row
        
        row = conn.execute(
            """
            SELECT date, sigma, grade, band_low, band_high
            FROM forecasts
            ORDER BY date DESC
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="예측 데이터가 없습니다."
            )

        return dict(row)

    finally:
        conn.close()