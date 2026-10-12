import fixtures from "./planner.fixtures.json";
import { allocateAmounts, buildPlan, resolveWeekdays } from "./planner";
import type { GradeLabel } from "./types";

const splitRule = fixtures.split_rule as Record<GradeLabel, number[]>;

describe("Python planner와 같은 결과 (planner.fixtures.json)", () => {
  it("케이스 36개 (등급 4 × 금액 3 × 주 3)", () => {
    expect(fixtures.cases).toHaveLength(36);
  });

  it.each(fixtures.cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const items = buildPlan(c.grade as GradeLabel, c.weekly_amount, splitRule, c.trading_weekdays);
    expect(
      items.map((it) => ({
        seq: it.seq,
        planned_weekday: it.plannedWeekday,
        trade_weekday: it.tradeWeekday,
        amount: it.amount,
      })),
    ).toEqual(c.expected);
  });
});

describe("planner 규칙", () => {
  it("금액 합계 = 주간 금액, 나머지는 마지막 회차", () => {
    expect(allocateAmounts(100_000, 3)).toEqual([33_333, 33_333, 33_334]);
    expect(allocateAmounts(7, 5)).toEqual([1, 1, 1, 1, 3]);
  });

  it("휴장이면 다음 거래일, 없으면 마지막 거래일", () => {
    expect(resolveWeekdays([0, 3], [1, 2, 4])).toEqual([1, 4]);
    expect(resolveWeekdays([4], [0, 1])).toEqual([1]);
  });

  it("forecast.json의 split_rule을 그대로 따른다", () => {
    expect(buildPlan("높음", 300_000, splitRule).map((it) => it.tradeWeekday)).toEqual([0, 2, 4]);
  });
});
