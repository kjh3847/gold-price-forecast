// 주간 분할 플랜 계산 (Python gold_service.planner 와 같은 규칙).
// 두 구현이 어긋나지 않는지 planner.fixtures.json 으로 테스트한다.
// 요일: 0=월 … 4=금

import type { GradeLabel } from "./types";

export const WEEKDAY_LABELS = ["월", "화", "수", "목", "금"];
export const ALL_WEEKDAYS = [0, 1, 2, 3, 4];

export interface PlanItem {
  seq: number;
  plannedWeekday: number; // 규칙상 요일
  tradeWeekday: number; // 휴장 이월 후 실제 요일
  amount: number; // 원
}

/** 회차 금액 = 주간 금액 ÷ n (원 단위 내림), 나머지는 마지막 회차에 더한다. */
export function allocateAmounts(weeklyAmount: number, n: number): number[] {
  if (!Number.isInteger(n) || n <= 0) throw new Error("분할 횟수는 1 이상이어야 합니다");
  const total = Math.floor(weeklyAmount);
  const base = Math.floor(total / n);
  const amounts = Array<number>(n).fill(base);
  amounts[n - 1] += total - base * n;
  return amounts;
}

/** 계획 요일이 휴장이면 그 주의 다음 거래일, 없으면 그 주 마지막 거래일로 옮긴다. */
export function resolveWeekdays(planned: number[], tradingWeekdays: number[]): number[] {
  const days = [...tradingWeekdays].sort((a, b) => a - b);
  if (days.length === 0) throw new Error("이번 주 거래일이 없습니다");
  return planned.map((wd) => days.find((d) => d >= wd) ?? days[days.length - 1]);
}

export function buildPlan(
  grade: GradeLabel,
  weeklyAmount: number,
  splitRule: Record<GradeLabel, number[]>,
  tradingWeekdays: number[] = ALL_WEEKDAYS,
): PlanItem[] {
  const planned = splitRule[grade];
  const trade = resolveWeekdays(planned, tradingWeekdays);
  const amounts = allocateAmounts(weeklyAmount, planned.length);
  return planned.map((wd, i) => ({
    seq: i + 1,
    plannedWeekday: wd,
    tradeWeekday: trade[i],
    amount: amounts[i],
  }));
}
