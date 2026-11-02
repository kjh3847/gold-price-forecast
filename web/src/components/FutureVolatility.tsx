import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Forecast } from "../types";

export function FutureVolatility({ data }: { data: Forecast }) {
  const points = data.volatility_projection;
  if (!points?.length) return null;
  return <section className="card" aria-labelledby="future-vol-title">
    <h2 id="future-vol-title">향후 5거래일 예상 변동성</h2>
    <p>기준일 {data.as_of} · 대상 {points[0].date} ~ {points[points.length - 1].date}</p>
    <p>예측 하루 변동성: ±{(data.sigma_daily * 100).toFixed(2)}%. 그래프는 같은 예측을 기간별로 환산한 값(σ × √거래일 수)입니다. 날짜별로 별도 예측한 변동성이나 가격 상승 경로가 아닙니다.</p>
    <div style={{ width: "100%", height: 260 }} role="img" aria-label="향후 5거래일 기간별 누적 변동성 환산 그래프">
      <ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tickFormatter={value => String(value).slice(5)} />
        <YAxis unit="%" domain={[0, "auto"]} />
        <Tooltip formatter={value => [`${Number(value).toFixed(2)}%`, "기간 변동성 환산"]} />
        <Line type="linear" dataKey="cumulative_sigma_pct" stroke="var(--accent)" strokeWidth={3} dot />
      </LineChart></ResponsiveContainer>
    </div>
    <table><caption>그래프 수치 (기간별 환산값)</caption><thead><tr><th>대상일</th><th>기간</th><th>변동성</th></tr></thead><tbody>{points.map(point => <tr key={point.date}><td>{point.date}</td><td>{point.horizon_day}거래일</td><td>±{point.cumulative_sigma_pct.toFixed(2)}%</td></tr>)}</tbody></table>
    <p>5거래일 뒤 예상 90% 가격 범위: {data.band.low.toLocaleString()} ~ {data.band.high.toLocaleString()} {data.currency}/{data.unit}. 위 변동성 그래프의 ±값 자체가 90% 범위는 아닙니다.</p>
    <p>‘향후 5거래일’은 기준일 다음 거래일부터이며 달력상 다음 주 월~금과 다를 수 있습니다.</p>
    {data.is_fallback && <p role="alert">모델 계산이 실패하여 최근 22일 실현 변동성을 사용한 대체 예측입니다.</p>}
  </section>;
}
