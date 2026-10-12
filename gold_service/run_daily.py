"""일간 배치 진입점.

    python -m gold_service.run_daily --date YYYY-MM-DD

수집 → 예측(필요 시 재학습, 누락일 백필) → 등급 → 저장 →
(주 첫 거래일이면) 주간 플랜 생성 + 모니터링.
같은 날짜로 다시 실행해도 결과가 중복되지 않는다.

종료 코드: 0 성공(휴장일 건너뜀 포함), 1 실패, 2 인자 오류, 3 거래일인데 가격 데이터 없음
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from gold_service import db
from gold_service.config import Settings
from gold_service.features import forward_variance, log_returns, realized_vol
from gold_service.grading import Grade, grade_from_percentile, percentile_of_last
from gold_service.models import forecast_positions
from gold_service.monitoring import MonitoringResult, compute_metrics, should_alert
from gold_service.notify import LogNotifier, Notifier
from gold_service.planner import build_plan
from gold_service.sources import PriceSource, build_source
from gold_service.trading_calendar import TradingCalendar, week_monday

log = logging.getLogger("gold_service")

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_NO_DATA = 0, 1, 2, 3


class DataMissingError(RuntimeError):
    pass


@dataclass
class RunResult:
    date: date
    status: str  # "ok" | "holiday"
    forecasts_written: int = 0
    retrained: list[date] = field(default_factory=list)
    sigma: float | None = None
    grade: str | None = None
    is_fallback: bool | None = None
    plans_written: int = 0
    monitoring: MonitoringResult | None = None


# ---------------------------------------------------------------- 단계
def collect(session: Session, source: PriceSource, target: date) -> pd.Series:
    df = source.fetch(None, target)
    added = db.upsert_prices(session, df, source.name)
    log.info("가격 수집: %d행 (신규 %d)", len(df), added)
    session.flush()
    return db.load_close(session, target)


def forecast(session: Session, close: pd.Series, backfill_days: int) -> tuple[pd.Series, list, list]:
    """예측이 없는 최근 거래일(백필 범위)과 오늘을 예측·저장한다."""
    r = log_returns(close)
    t_pos = len(r) - 1
    existing = db.forecast_dates(session, r.index[-1].date())
    start = max(0, t_pos - backfill_days + 1)
    positions = [p for p in range(start, t_pos + 1) if p == t_pos or r.index[p].date() not in existing]
    if len(positions) > 1:
        log.info("백필: %d개 거래일 예측 (%s ~ %s)", len(positions), r.index[positions[0]].date(), r.index[t_pos].date())

    forecasts, new_params = forecast_positions(r, positions, db.load_params(session))
    for p in new_params:
        db.save_params(session, p)
    for fc in forecasts:
        db.save_forecast(session, fc)
    session.flush()
    return r, forecasts, new_params


def grade(session: Session, dates: list[date], end: date) -> None:
    """각 날짜의 백분위·등급을 그날까지의 예측값만으로 계산한다."""
    sigma = db.load_forecasts(session, end)["sigma"]
    for d in sorted(dates):
        pct = percentile_of_last(sigma.loc[: pd.Timestamp(d)].to_numpy())
        db.save_grade(session, d, pct, grade_from_percentile(pct))
    session.flush()


def is_first_trading_day_of_week(close: pd.Series, target: date) -> bool:
    monday = pd.Timestamp(week_monday(target))
    earlier = close.index[(close.index >= monday) & (close.index < pd.Timestamp(target))]
    return len(earlier) == 0


def make_plans(
    session: Session, r: pd.Series, target: date, calendar: TradingCalendar, notifier: Notifier
) -> int:
    """직전 거래일 종가 기준 σ·등급으로 이번 주 플랜을 만든다."""
    if len(r) < 2:
        log.warning("직전 거래일이 없어 플랜을 만들 수 없습니다")
        return 0
    prev = r.index[-2].date()
    forecasts = db.load_forecasts(session, prev)
    if forecasts.empty or forecasts.index[-1].date() != prev or pd.isna(forecasts.iloc[-1]["grade"]):
        log.warning("직전 거래일(%s) 예측·등급이 없어 플랜을 건너뜁니다", prev)
        return 0
    row = forecasts.iloc[-1]
    trading_days = sorted({d for d in calendar.trading_days_in_week(target) if d >= target} | {target})

    users = db.active_users(session)
    if not users:
        log.info("활성 사용자가 없어 플랜을 만들지 않습니다 (python -m gold_service.manage add-user 참고)")
    for user in users:
        plan = build_plan(
            grade=Grade(row["grade"]),
            sigma=float(row["sigma"]),
            forecast_date=prev,
            weekly_amount=int(user.weekly_amount),
            trading_days=trading_days,
        )
        db.replace_plan(session, user.id, plan)
        notifier.plan_created(user.id, user.name, plan)
    session.flush()
    return len(users)


def monitor(session: Session, r: pd.Series, target: date, notifier: Notifier) -> MonitoringResult:
    forecasts = db.load_forecasts(session, target)
    result = compute_metrics(
        as_of=target,
        sigma=forecasts["sigma"],
        realized_var=forward_variance(r).reindex(forecasts.index),  # r이 target에서 끝나므로 확정분만 값이 있다
        baseline_sigma=realized_vol(r, 22).reindex(forecasts.index),
    )
    result.alert = should_alert(db.previous_improvements(session, target) + [result.improvement])
    db.save_monitoring(session, result)
    log.info(
        "모니터링(최근 13주, n=%d): 적중률 %s, 개선율 %s",
        result.n_obs,
        f"{result.hit_rate:.1%}" if result.hit_rate is not None else "-",
        f"{result.improvement:+.2%}" if result.improvement is not None else "-",
    )
    if result.alert:
        notifier.monitoring_alert(result)
    return result


# ---------------------------------------------------------------- 실행
def run(
    target: date,
    settings: Settings | None = None,
    source: PriceSource | None = None,
    calendar: TradingCalendar | None = None,
    notifier: Notifier | None = None,
) -> RunResult:
    settings = settings or Settings.from_env()
    source = source or build_source(settings)
    calendar = calendar or TradingCalendar.from_file(settings.holidays_file)
    notifier = notifier or LogNotifier()

    engine = db.make_engine(settings.database_url)
    db.init_db(engine)
    with Session(engine) as session, session.begin():
        close = collect(session, source, target)
        if pd.Timestamp(target) not in close.index:
            if not calendar.is_trading_day(target):
                log.info("%s 휴장일 — 건너뜀", target)
                return RunResult(target, "holiday")
            raise DataMissingError(
                f"{target} 은 거래일인데 가격 데이터가 없습니다 (휴장일이면 HOLIDAYS_FILE에 추가하세요)"
            )

        r, forecasts, new_params = forecast(session, close, settings.backfill_days)
        grade(session, [f.date for f in forecasts], target)
        today = db.load_forecasts(session, target).iloc[-1]
        result = RunResult(
            target,
            "ok",
            forecasts_written=len(forecasts),
            retrained=[p.trained_on for p in new_params],
            sigma=float(today["sigma"]),
            grade=None if pd.isna(today["grade"]) else today["grade"],
            is_fallback=bool(today["is_fallback"]),
        )
        log.info(
            "%s 예측: σ=%.4f (하루 ±%.2f%%), 등급=%s, 대체값=%s",
            target, result.sigma, result.sigma * 100, result.grade, result.is_fallback,
        )

        if is_first_trading_day_of_week(close, target):
            log.info("주 첫 거래일 — 플랜 생성·모니터링 실행")
            result.plans_written = make_plans(session, r, target, calendar, notifier)
            result.monitoring = monitor(session, r, target, notifier)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="금 분할매수 도우미 일간 배치")
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="기준일 YYYY-MM-DD (장 마감 후 실행)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    try:
        run(args.date, settings)
    except DataMissingError as exc:
        log.error(str(exc))
        return EXIT_NO_DATA
    except Exception:
        log.exception("일간 배치 실패 (%s)", args.date)
        return EXIT_FAIL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
