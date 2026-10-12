"""3. 플랜 테스트: 등급별 분할 횟수·요일, 휴장일 이월, 금액 합계 = 주간 금액."""
import math
from datetime import date, timedelta

import pytest

from gold_service.grading import Grade, grade_from_percentile, percentile_of_last
from gold_service.planner import allocate_amounts, build_plan, resolve_trade_dates
from gold_service.trading_calendar import TradingCalendar

MONDAY = date(2026, 10, 5)
WEEK = [MONDAY + timedelta(days=i) for i in range(5)]  # 월~금


def plan(grade, trading_days=WEEK, amount=300_000):
    return build_plan(grade=grade, sigma=0.012, forecast_date=MONDAY - timedelta(days=3),
                      weekly_amount=amount, trading_days=trading_days)


@pytest.mark.parametrize(
    "grade, weekdays",
    [
        (Grade.LOW, [0]),
        (Grade.NORMAL, [0, 3]),
        (Grade.HIGH, [0, 2, 4]),
        (Grade.VERY_HIGH, [0, 1, 2, 3, 4]),
    ],
)
def test_split_count_and_weekdays(grade, weekdays):
    p = plan(grade)
    assert [it.trade_date.weekday() for it in p.items] == weekdays
    assert [it.planned_weekday for it in p.items] == weekdays
    assert all(it.order_type == "MARKET" for it in p.items)
    assert p.week_start == MONDAY


def test_holiday_rolls_to_next_trading_day():
    cal = TradingCalendar({WEEK[0], WEEK[3]})  # 월·목 휴장
    days = cal.trading_days_in_week(MONDAY)
    assert [it.trade_date for it in plan(Grade.NORMAL, days).items] == [WEEK[1], WEEK[4]]


def test_holiday_with_no_later_day_uses_last_trading_day():
    days = WEEK[:4]  # 금 휴장
    assert [it.trade_date for it in plan(Grade.HIGH, days).items] == [WEEK[0], WEEK[2], WEEK[3]]
    assert resolve_trade_dates([4], [WEEK[0], WEEK[1]]) == [WEEK[1]]


@pytest.mark.parametrize("amount", [300_000, 100_000, 99_999, 7])
@pytest.mark.parametrize("grade", list(Grade))
def test_amounts_sum_to_weekly_amount(grade, amount):
    p = plan(grade, amount=amount)
    amounts = [it.amount for it in p.items]
    assert sum(amounts) == amount
    assert all(isinstance(a, int) for a in amounts)


def test_remainder_goes_to_last_item():
    assert allocate_amounts(100_000, 3) == [33_333, 33_333, 33_334]
    assert allocate_amounts(100_003, 5) == [20_000, 20_000, 20_000, 20_000, 20_003]


def test_plan_contains_sigma_and_5day_range():
    p = plan(Grade.HIGH)
    assert p.sigma == 0.012
    assert p.range_5d == pytest.approx(0.012 * math.sqrt(5))
    assert "±1.20%" in p.summary() and "±2.68%" in p.summary()


def test_grade_thresholds():
    assert grade_from_percentile(None) is None
    assert grade_from_percentile(33) is Grade.LOW
    assert grade_from_percentile(33.1) is Grade.NORMAL
    assert grade_from_percentile(67) is Grade.NORMAL
    assert grade_from_percentile(90) is Grade.HIGH
    assert grade_from_percentile(90.1) is Grade.VERY_HIGH


def test_percentile_needs_60_and_uses_last_252():
    assert percentile_of_last(list(range(59))) is None
    assert percentile_of_last(list(range(60))) == 100.0
    values = [1000.0] * 100 + list(range(252))  # 앞의 100개는 창 밖
    assert percentile_of_last(values) == 100.0
    assert percentile_of_last(values[:-1] + [0.5]) == pytest.approx(100 * 2 / 252)  # 0, 0.5
