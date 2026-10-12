"""주간 분할매수 플랜 생성 (MVP: 시장가만).

나중에 지정가 등을 붙일 수 있도록 단계별 함수로 나눠 둔다:
  split_weekdays → resolve_trade_dates → allocate_amounts → build_plan
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from gold_service.features import HORIZON
from gold_service.grading import Grade
from gold_service.trading_calendar import week_monday

MON, TUE, WED, THU, FRI = range(5)
WEEKDAY_LABELS = ["월", "화", "수", "목", "금"]

SPLIT_RULES: dict[Grade, list[int]] = {
    Grade.LOW: [MON],
    Grade.NORMAL: [MON, THU],
    Grade.HIGH: [MON, WED, FRI],
    Grade.VERY_HIGH: [MON, TUE, WED, THU, FRI],
}

DISCLAIMER = "이 플랜은 예상 변동성에 따라 매수 시점을 나누는 일정 안내이며, 금값 방향 예측이나 투자 권유가 아니고 수익을 보장하지 않습니다."


@dataclass
class PlanItem:
    seq: int
    planned_weekday: int
    trade_date: date
    amount: int
    order_type: str = "MARKET"


@dataclass
class WeeklyPlan:
    week_start: date  # 해당 주 월요일
    forecast_date: date  # 사용한 예측의 기준일(직전 거래일)
    grade: Grade
    sigma: float  # 하루 변동성 (소수, 0.012 = ±1.2%)
    range_5d: float  # σ × √5
    weekly_amount: int
    items: list[PlanItem] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"이번 주 변동성 등급: {self.grade.label}",
            f"예상 변동폭: 하루 ±{self.sigma * 100:.2f}%, 5거래일 ±{self.range_5d * 100:.2f}%",
            f"분할 계획 ({len(self.items)}회):",
        ]
        lines += [
            f"  {it.seq}회차 {it.trade_date.isoformat()}({WEEKDAY_LABELS[it.trade_date.weekday()]}) {it.amount:,}원"
            for it in self.items
        ]
        lines.append(DISCLAIMER)
        return "\n".join(lines)


def split_weekdays(grade: Grade) -> list[int]:
    """등급별 계획 요일 목록 (길이 = 분할 횟수)."""
    return list(SPLIT_RULES[grade])


def resolve_trade_dates(weekdays: list[int], trading_days: list[date]) -> list[date]:
    """계획 요일을 실제 거래일로 바꾼다.

    휴장이면 그 주의 다음 거래일로 미루고, 다음 거래일이 없으면 그 주 마지막 거래일.
    trading_days: 그 주의 거래일 목록 (오름차순, 비어 있으면 안 됨)
    """
    if not trading_days:
        raise ValueError("이번 주 거래일이 없습니다")
    monday = week_monday(trading_days[0])
    result = []
    for wd in weekdays:
        target = monday.toordinal() + wd
        later = [d for d in trading_days if d.toordinal() >= target]
        result.append(later[0] if later else trading_days[-1])
    return result


def allocate_amounts(weekly_amount: int, n: int) -> list[int]:
    """회차 금액 = 주간 금액 ÷ n (원 단위 내림), 나머지는 마지막 회차에 더한다."""
    if n <= 0:
        raise ValueError("분할 횟수는 1 이상이어야 합니다")
    base = weekly_amount // n
    amounts = [base] * n
    amounts[-1] += weekly_amount - base * n
    return amounts


def build_plan(
    *,
    grade: Grade,
    sigma: float,
    forecast_date: date,
    weekly_amount: int,
    trading_days: list[date],
) -> WeeklyPlan:
    weekdays = split_weekdays(grade)
    dates = resolve_trade_dates(weekdays, trading_days)
    amounts = allocate_amounts(weekly_amount, len(weekdays))
    items = [
        PlanItem(seq=i + 1, planned_weekday=wd, trade_date=d, amount=a)
        for i, (wd, d, a) in enumerate(zip(weekdays, dates, amounts))
    ]
    return WeeklyPlan(
        week_start=week_monday(trading_days[0]),
        forecast_date=forecast_date,
        grade=grade,
        sigma=sigma,
        range_5d=sigma * math.sqrt(HORIZON),
        weekly_amount=weekly_amount,
        items=items,
    )
