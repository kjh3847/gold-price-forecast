"""Append dated prices and refresh the existing model in one DB transaction."""
import csv
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from gold_service import db
from gold_service.export_json import build_payload
from gold_service.run_daily import forecast, grade, bands
from gold_service.trading_calendar import TradingCalendar

SOURCE_URL = "https://goldprice.com/gold-price-history"
DOWNLOAD_URL = "https://goldprice.com/gold-price-history.csv"
STALE_DAYS = 5


def last_completed_day(calendar, now=None):
    # Conservative: today's NY close is never assumed available. No intraday data.
    market_date = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("America/New_York")).date()
    day = market_date - timedelta(days=1)
    while not calendar.is_trading_day(day):
        day -= timedelta(days=1)
    return day


def trading_dates(start, end, calendar):
    result = []
    day = start
    while day <= end:
        if calendar.is_trading_day(day):
            result.append(day)
        day += timedelta(days=1)
    return result


def status(session, settings, now=None):
    calendar = TradingCalendar.from_file(settings.holidays_file)
    expected = last_completed_day(calendar, now)
    latest = session.scalar(select(func.max(db.Price.date)))
    latest_forecast = session.scalar(select(func.max(db.ForecastRow.date)))
    missing = trading_dates(latest + timedelta(days=1), expected, calendar) if latest else []
    return {
        "last_price_date": latest, "last_forecast_date": latest_forecast,
        "expected_through": expected, "missing_count": len(missing),
        "required_from": missing[0] if missing else None,
        "required_to": missing[-1] if missing else None,
        "missing_dates": missing, "needs_upload": latest is None or len(missing) >= STALE_DAYS,
        "threshold_trading_days": STALE_DAYS, "source_url": SOURCE_URL,
        "download_url": DOWNLOAD_URL, "currency": "USD", "unit": "oz",
        "calendar_note": "주말만 제외" if settings.holidays_file is None else "설정된 휴장일 반영",
        "cutoff_note": "뉴욕 날짜 기준 전일까지 확정된 종가만 사용",
    }


def parse_csv(text, calendar, expected):
    lines = (line for line in text.lstrip('\ufeff').splitlines() if line.strip() and not line.lstrip().startswith('#'))
    reader = csv.DictReader(lines)
    headers = reader.fieldnames or []
    price_column = next((col for col in ("close_usd_per_troy_oz", "gold", "close") if col in headers), None)
    if "date" not in headers or price_column is None:
        raise ValueError("CSV에 date와 close_usd_per_troy_oz (또는 gold, close) 열이 필요합니다.")
    prices, skipped = {}, 0
    for number, row in enumerate(reader, 2):
        if number > 40000:
            raise ValueError("CSV는 40,000행 이하만 지원합니다.")
        try:
            day = date.fromisoformat(row["date"].strip())
            value = float(row[price_column])
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f"CSV {number}행의 날짜 또는 가격 형식이 잘못됐습니다.") from None
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"CSV {number}행의 가격은 유한한 양수여야 합니다.")
        if not calendar.is_trading_day(day):
            skipped += 1
            continue
        if day > expected:
            raise ValueError(f"{day}: 아직 확정 대상으로 인정하지 않는 날짜입니다. {expected}까지 올려주세요.")
        if day in prices and prices[day] != value:
            raise ValueError(f"{day}: 서로 다른 중복 가격이 있습니다.")
        prices[day] = value
    if not prices:
        raise ValueError("CSV에 사용 가능한 거래일 가격이 없습니다.")
    return prices, skipped


def import_prices(session, text, settings, now=None):
    before = status(session, settings, now)
    calendar = TradingCalendar.from_file(settings.holidays_file)
    prices, skipped = parse_csv(text, calendar, before["expected_through"])
    existing = {row.date: row.close for row in session.scalars(select(db.Price))}
    conflicts = [day for day, value in prices.items() if day in existing and not math.isclose(existing[day], value, rel_tol=0, abs_tol=1e-6)]
    if conflicts:
        raise ValueError(f"기존 가격과 다른 데이터가 있습니다: {min(conflicts)}. 기존 기록은 덮어쓰지 않습니다.")
    latest = max(existing) if existing else None
    added = {day: value for day, value in prices.items() if latest is None or day > latest}
    if not added:
        raise ValueError("추가할 최신 가격이 없습니다. 사이트에서 최신 CSV를 다시 내려받으세요.")
    if latest:
        missing = [day for day in before["missing_dates"] if day not in added]
        if missing:
            raise ValueError(f"{missing[0]}부터 {missing[-1]}까지 {len(missing)}거래일이 아직 부족합니다. 필요한 전체 기간을 포함해 주세요.")
    else:
        missing = [day for day in trading_dates(min(added), before["expected_through"], calendar) if day not in added]
        if missing:
            raise ValueError(f"{missing[0]} 등 누락된 거래일이 있습니다. 휴장일 설정 또는 CSV를 확인하세요.")
    for day, value in sorted(added.items()):
        session.add(db.Price(date=day, close=value, source="goldprice_upload"))
    session.flush()
    target = max(added)
    close = db.load_close(session, target)
    if len(close) < 280:
        raise ValueError("기존 모델 학습을 위해 최소 280개 가격 관측값이 필요합니다.")
    _, forecasts, trained = forecast(session, close, settings.backfill_days)
    dates = [item.date for item in forecasts]
    grade(session, dates, target)
    bands(session, close, dates, target)
    payload = build_payload(session)
    # Caller commits only after forecast serialization and all validation succeed.
    return {"added_count": len(added), "skipped_nontrading_rows": skipped,
            "retrained_dates": [p.trained_on for p in trained], "forecast": payload,
            "data_status": status(session, settings, now)}
