import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { formatDate, formatMonthTick, formatNumber } from "../format";
import type { Forecast } from "../types";

export function LongRangeCard({ data }: { data: Forecast }) {
  const projection = data.long_range;
  if (!projection?.length) return null;

  const historical = data.history.filter((p) => p.date < data.as_of && p.price !== null).slice(-126);
  const points = [
    ...historical.filter((_, index) => index % 21 === 0).map((p) => ({ date: p.date, price: p.price })),
    { date: data.as_of, price: data.price, median: data.price, range: [data.price, data.price] },
    ...projection.map((p) => ({ date: p.date, median: p.median, range: [p.low, p.high] })),
  ];
  const unit = `${data.currency}/${data.unit}`;

  return (
    <section className="card" aria-labelledby="long-range-title">
      <h2 id="long-range-title" className="card__title">향후 6개월 금 가격 전망</h2>
      <p className="hint">
        기준일 {formatDate(data.as_of)} · {unit} · 최근 5년간 같은 기간의 가격 변화를 바탕으로 중앙 90% 범위를 계산했어요.
      </p>
      <figure className="chart">
        <ul className="legend" aria-label="범례">
          <li><span className="legend__swatch legend__swatch--line" aria-hidden="true" />과거 종가</li>
          <li><span className="legend__swatch legend__swatch--band" aria-hidden="true" />예상 범위</li>
          <li>점선 · 예상 중앙값</li>
        </ul>
        <div className="chart__plot" role="img" aria-label="과거 종가와 향후 6개월 예상 가격 범위 및 중앙값">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="date" tickFormatter={formatMonthTick} tick={{ fill: "var(--text-muted)", fontSize: 12 }} minTickGap={24} />
              <YAxis domain={["auto", "auto"]} tickFormatter={(value: number) => formatNumber(value)} tick={{ fill: "var(--text-muted)", fontSize: 12 }} width={52} />
              <Area dataKey="range" stroke="none" fill="var(--band)" isAnimationActive={false} />
              <Line dataKey="price" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="median" stroke="var(--series-1)" strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </figure>
      <details className="table-view">
        <summary>월별 전망 수치 보기</summary>
        <table>
          <thead><tr><th scope="col">기준일로부터</th><th scope="col">예상일</th><th scope="col">가격 범위</th><th scope="col">중앙값</th></tr></thead>
          <tbody>
            {projection.map((p) => (
              <tr key={p.months}>
                <th scope="row">{p.months}개월</th><td>{p.date}</td>
                <td>{formatNumber(p.low)} ~ {formatNumber(p.high)}</td><td>{formatNumber(p.median)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
