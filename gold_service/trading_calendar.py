"""거래일 달력. 이번 주의 남은 거래일(미래)을 알아야 플랜 날짜를 정할 수 있다."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class TradingCalendar:
    """월~금 중 휴장일 목록에 없는 날을 거래일로 본다."""

    def __init__(self, holidays: set[date] | None = None):
        self.holidays = set(holidays or ())

    @classmethod
    def from_file(cls, path: Path | None) -> "TradingCalendar":
        """휴장일 CSV(첫 컬럼 date, YYYY-MM-DD)를 읽는다. 경로가 없으면 주말만 휴장."""
        if path is None:
            return cls()
        df = pd.read_csv(path, encoding="utf-8-sig")
        return cls(set(pd.to_datetime(df.iloc[:, 0]).dt.date))

    def is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def trading_days_in_week(self, d: date) -> list[date]:
        monday = week_monday(d)
        return [monday + timedelta(days=i) for i in range(5) if self.is_trading_day(monday + timedelta(days=i))]
