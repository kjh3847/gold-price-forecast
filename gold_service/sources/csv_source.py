"""CSV 파일 가격 소스 (현재: 달러 금값 gold_only_ready.csv)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from gold_service.sources.base import PriceSource


class CSVPriceSource(PriceSource):
    name = "csv"

    def __init__(
        self,
        path: str | Path,
        date_col: str = "date",
        close_col: str = "gold",
        open_col: str | None = None,
        high_col: str | None = None,
        low_col: str | None = None,
    ):
        self.path = Path(path)
        self.columns = {
            date_col: "date",
            close_col: "close",
            **{c: n for c, n in ((open_col, "open"), (high_col, "high"), (low_col, "low")) if c},
        }

    def fetch(self, start: date | None, end: date) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"가격 CSV를 찾을 수 없습니다: {self.path}")
        raw = pd.read_csv(self.path, encoding="utf-8-sig", usecols=list(self.columns))
        df = self.normalize(raw.rename(columns=self.columns))
        mask = df["date"] <= end
        if start is not None:
            mask &= df["date"] >= start
        return df[mask].reset_index(drop=True)
