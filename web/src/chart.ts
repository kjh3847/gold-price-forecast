import type { HistoryPoint } from "./types";

export interface ChartPoint {
  date: string;
  price: number | null;
  low: number | null; // horizon 거래일 전에 낸 범위
  high: number | null;
  range: [number, number] | null; // Recharts 범위 Area 용
  outside: number | null; // 범위를 벗어난 날의 가격 (점 표시)
}

/**
 * 각 날짜의 실제 가격과 "그 날짜에 해당하는 범위"를 묶는다.
 * history[j−h]의 band는 j−h 종가 기준 다음 h거래일 범위이므로 날짜 j에 그린다.
 */
export function buildChartData(history: HistoryPoint[], horizon = 5): ChartPoint[] {
  return history.map((point, j) => {
    const issued = j >= horizon ? history[j - horizon] : undefined;
    const low = issued?.band_low ?? null;
    const high = issued?.band_high ?? null;
    const hasBand = low !== null && high !== null;
    const price = point.price;
    const isOutside = hasBand && price !== null && (price < low || price > high);
    return {
      date: point.date,
      price,
      low,
      high,
      range: hasBand ? [low, high] : null,
      outside: isOutside ? price : null,
    };
  });
}

export function outsideStats(points: ChartPoint[]): { checked: number; outside: number } {
  const checked = points.filter((p) => p.range !== null && p.price !== null).length;
  const outside = points.filter((p) => p.outside !== null).length;
  return { checked, outside };
}
