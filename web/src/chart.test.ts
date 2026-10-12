import { buildChartData, outsideStats } from "./chart";
import type { HistoryPoint } from "./types";

const point = (date: string, price: number, low: number, high: number): HistoryPoint => ({
  date,
  price,
  sigma_daily: 0.01,
  grade: "보통",
  band_low: low,
  band_high: high,
});

describe("buildChartData", () => {
  const history = [
    point("2026-01-01", 100, 90, 110),
    point("2026-01-02", 101, 91, 111),
    point("2026-01-05", 102, 92, 112),
    point("2026-01-06", 103, 93, 113),
    point("2026-01-07", 104, 94, 114),
    point("2026-01-08", 105, 95, 115), // 01-01 범위(90~110) 안
    point("2026-01-09", 120, 96, 116), // 01-02 범위(91~111) 밖
  ];

  it("5거래일 전에 낸 범위를 그 날짜에 붙인다", () => {
    const data = buildChartData(history, 5);
    expect(data.slice(0, 5).every((p) => p.range === null)).toBe(true);
    expect(data[5].range).toEqual([90, 110]);
    expect(data[6].range).toEqual([91, 111]);
  });

  it("범위를 벗어난 날만 outside에 가격이 들어간다", () => {
    const data = buildChartData(history, 5);
    expect(data[5].outside).toBeNull();
    expect(data[6].outside).toBe(120);
    expect(outsideStats(data)).toEqual({ checked: 2, outside: 1 });
  });
});
