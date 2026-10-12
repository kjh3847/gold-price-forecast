"""환경변수 기반 설정."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_url: str
    price_source: str
    price_csv_path: Path
    price_csv_date_col: str
    price_csv_close_col: str
    holidays_file: Path | None
    backfill_days: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        holidays = os.getenv("HOLIDAYS_FILE")
        return cls(
            database_url=os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'gold_service.db'}"),
            price_source=os.getenv("PRICE_SOURCE", "csv"),
            price_csv_path=Path(os.getenv("PRICE_CSV_PATH", str(PROJECT_ROOT / "data" / "gold_only_ready.csv"))),
            price_csv_date_col=os.getenv("PRICE_CSV_DATE_COL", "date"),
            price_csv_close_col=os.getenv("PRICE_CSV_CLOSE_COL", "gold"),
            holidays_file=Path(holidays) if holidays else None,
            backfill_days=int(os.getenv("BACKFILL_DAYS", "400")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
