"""로컬 개발용 관리 명령 (사용자 기능 본 구현 전 임시).

    python -m gold_service.manage add-user --name 홍길동 --weekly-amount 300000
    python -m gold_service.manage show-plans
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from gold_service import db
from gold_service.config import Settings
from gold_service.grading import Grade
from gold_service.planner import PlanItem, WeeklyPlan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="금 분할매수 도우미 관리 명령")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add-user", help="사용자 추가")
    add.add_argument("--name", required=True)
    add.add_argument("--weekly-amount", required=True, type=int, help="주간 매수 금액(원)")
    sub.add_parser("show-plans", help="사용자별 최신 플랜 출력")
    args = parser.parse_args(argv)

    engine = db.make_engine(Settings.from_env().database_url)
    db.init_db(engine)
    with Session(engine) as session, session.begin():
        if args.cmd == "add-user":
            if args.weekly_amount <= 0:
                parser.error("--weekly-amount는 양수여야 합니다")
            user = db.add_user(session, args.name, args.weekly_amount)
            print(f"사용자 추가: id={user.id} {user.name} 주간 {user.weekly_amount:,}원")
        else:
            for user in db.active_users(session):
                row = session.scalar(
                    select(db.BuyPlan).where(db.BuyPlan.user_id == user.id).order_by(db.BuyPlan.week_start.desc())
                )
                print(f"== {user.name} (id={user.id})")
                if row is None:
                    print("플랜 없음")
                    continue
                plan = WeeklyPlan(
                    week_start=row.week_start, forecast_date=row.forecast_date, grade=Grade(row.grade),
                    sigma=row.sigma, range_5d=row.range_5d, weekly_amount=row.weekly_amount,
                    items=[PlanItem(i.seq, i.planned_weekday, i.trade_date, i.amount, i.order_type) for i in row.items],
                )
                print(plan.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
