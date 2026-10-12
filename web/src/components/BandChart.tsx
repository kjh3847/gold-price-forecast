import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";
import type { ChartPoint } from "../chart";
import { formatDate, formatMonthTick, formatNumber } from "../format";

interface Props {
  points: ChartPoint[];
  unit: string;
}

function ChartTooltip({ active, payload, unit }: TooltipProps<number, string> & { unit: string }) {
  const p = payload?.[0]?.payload as ChartPoint | undefined;
  if (!active || !p) return null;
  return (
    <div className="tooltip">
      <p className="tooltip__date">{formatDate(p.date)}</p>
      <p>
        가격 <strong>{p.price === null ? "-" : `${formatNumber(p.price, 2)} ${unit}`}</strong>
      </p>
      <p>
        범위 {p.low === null || p.high === null ? "-" : `${formatNumber(p.low)} ~ ${formatNumber(p.high)}`}
      </p>
      {p.outside !== null && <p className="tooltip__outside">● 범위를 벗어남</p>}
    </div>
  );
}

// 월이 바뀌는 첫 거래일만 눈금으로 쓴다
function monthTicks(points: ChartPoint[]): string[] {
  return points.filter((p, i) => i > 0 && p.date.slice(0, 7) !== points[i - 1].date.slice(0, 7)).map((p) => p.date);
}

export function BandChart({ points, unit }: Props) {
  return (
    <figure className="chart">
      <ul className="legend" aria-label="범례">
        <li>
          <span className="legend__swatch legend__swatch--line" aria-hidden="true" />
          실제 가격
        </li>
        <li>
          <span className="legend__swatch legend__swatch--band" aria-hidden="true" />
          90% 범위 (5거래일 전 예측)
        </li>
        <li>
          <span className="legend__swatch legend__swatch--dot" aria-hidden="true" />
          범위를 벗어난 날
        </li>
      </ul>
      <div className="chart__plot" role="img" aria-label="최근 260거래일 실제 가격과 5거래일 전에 예측한 90% 범위">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis
              dataKey="date"
              ticks={monthTicks(points)}
              tickFormatter={formatMonthTick}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--axis)" }}
              minTickGap={24}
            />
            <YAxis
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => formatNumber(v)}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              content={<ChartTooltip unit={unit} />}
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Area
              dataKey="range"
              stroke="none"
              fill="var(--band)"
              fillOpacity={1}
              isAnimationActive={false}
              activeDot={false}
            />
            <Line
              dataKey="price"
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {/* 값이 있는 날(범위를 벗어난 날)에만 점이 찍힌다 */}
            <Line
              dataKey="outside"
              stroke="none"
              dot={{ r: 5, fill: "var(--series-2)", stroke: "var(--surface)", strokeWidth: 2 }}
              activeDot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
