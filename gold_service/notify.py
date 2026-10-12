"""알림 인터페이스. 현재는 로그만 남긴다 (알림 발송은 범위 밖).

웹 푸시·카카오톡·이메일 등은 Notifier를 구현해 run_daily.run(notifier=...)로 넘기면 된다.
"""
from __future__ import annotations

import logging
from typing import Protocol

from gold_service.monitoring import MonitoringResult
from gold_service.planner import WeeklyPlan

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def plan_created(self, user_id: int, user_name: str, plan: WeeklyPlan) -> None: ...

    def monitoring_alert(self, result: MonitoringResult) -> None: ...


class LogNotifier:
    def plan_created(self, user_id: int, user_name: str, plan: WeeklyPlan) -> None:
        log.info("플랜 생성 (user=%s %s, week=%s)\n%s", user_id, user_name, plan.week_start, plan.summary())

    def monitoring_alert(self, result: MonitoringResult) -> None:
        log.warning(
            "[경보] 단순 기준(rv22) 대비 개선율이 4주 연속 0%% 미만입니다 (%s, 개선율 %.2f%%). 모델 점검이 필요합니다.",
            result.date,
            (result.improvement or 0) * 100,
        )
