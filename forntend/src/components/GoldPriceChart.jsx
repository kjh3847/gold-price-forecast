import { ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { money, dateLabel } from '../utils/format.js';

function PriceTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{dateLabel(label)}</strong>{payload.map((item) => <div key={item.dataKey}><span style={{ color: item.color }}>{item.name}</span><b>{money(item.value)}</b></div>)}</div>;
}
export default function GoldPriceChart({ rows, period, onPeriodChange, compare, onCompareChange, title = '금 시세 추이', subtitle = '과거 가격의 흐름과 예측 데이터를 비교해보세요.', id = 'price' }) {
  return <section className="panel chart-panel"><div className="panel-heading"><div><h2>{title}</h2><p>{subtitle}</p></div>{onPeriodChange && <div className="period-control" aria-label="차트 조회 기간">{['1M', '3M', '6M', '1Y'].map((item) => <button key={item} aria-pressed={period === item} onClick={() => onPeriodChange(item)}>{item}</button>)}</div>}</div>
    <div className="chart-meta"><div className="legend"><span><i className="legend-line actual" />실제 가격 (mock)</span>{compare && <span><i className="legend-line forecast" />예측 가격 (mock)</span>}</div>{onCompareChange && <label className="compare-toggle"><input type="checkbox" checked={compare} onChange={(e) => onCompareChange(e.target.checked)} />예측값 비교</label>}</div>
    <div className="chart-unit">KRW / g</div><div className="chart-container" role="img" aria-label={`${title}: ${rows.length}개 일별 금 가격${compare ? ', 실제값과 예측값 비교' : ''}`}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}><ComposedChart data={rows} margin={{ top: 12, right: 12, left: 4, bottom: 4 }} accessibilityLayer>
        <defs><linearGradient id={`${id}-goldFill`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c49a39" stopOpacity={0.2} /><stop offset="100%" stopColor="#c49a39" stopOpacity={0.015} /></linearGradient></defs>
        <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#eceeea" /><XAxis dataKey="date" tickFormatter={(date) => date.slice(5).replace('-', '.')} minTickGap={38} tick={{ fill: '#969a9e', fontSize: 11 }} axisLine={false} tickLine={false} dy={10} /><YAxis domain={['auto', 'auto']} tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`} tick={{ fill: '#969a9e', fontSize: 11 }} axisLine={false} tickLine={false} width={47} /><Tooltip content={<PriceTooltip />} />
        <Area type="monotone" dataKey="close" name="실제 가격" stroke="#b58b31" fill={`url(#${id}-goldFill)`} strokeWidth={2.4} isAnimationActive={false} />
        {compare && <Line type="monotone" dataKey="predicted" name="예측 가격" stroke="#839591" strokeWidth={1.8} strokeDasharray="5 5" dot={false} isAnimationActive={false} />}
      </ComposedChart></ResponsiveContainer>
    </div><div className="chart-footnote"><span>{rows[0]?.date} — {rows.at(-1)?.date}</span><span>{rows.length}개 관측값 · 일별 종가</span></div>
  </section>;
}
