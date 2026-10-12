"""가격 데이터 소스 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

# 시가·고가·저가는 소스가 제공하지 않으면 NaN으로 둔다. 모델은 close만 사용한다.
PRICE_COLUMNS = ["date", "open", "high", "low", "close"]


class PriceSource(ABC):
    """일간 가격 시계열 제공자.

    구현체는 `fetch`에서 PRICE_COLUMNS 컬럼을 가진 DataFrame을 돌려줘야 한다.
    - date: datetime.date, 오름차순, 중복 없음
    - close: 양수 float (NaN 금지)
    """

    name: str = "base"

    @abstractmethod
    def fetch(self, start: date | None, end: date) -> pd.DataFrame:
        """[start, end] 구간(양끝 포함)의 일간 가격을 반환한다. start=None이면 처음부터."""

    @staticmethod
    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        """공통 정리: 컬럼 보정, 정렬, 중복·결측 제거, 검증."""
        out = df.copy()
        for col in PRICE_COLUMNS:
            if col not in out.columns:
                out[col] = float("nan")
        out = out[PRICE_COLUMNS]
        out["date"] = pd.to_datetime(out["date"]).dt.date
        out["close"] = pd.to_numeric(out["close"], errors="coerce")
        out = out.dropna(subset=["close"])
        out = out.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
        if (out["close"] <= 0).any():
            raise ValueError("close 값에 0 이하가 있습니다")
        return out
