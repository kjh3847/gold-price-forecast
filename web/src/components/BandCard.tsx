import { useMemo } from "react";
import { buildChartData, outsideStats } from "../chart";
import { currencyLabel, formatNumber, formatPct, halfWidth } from "../format";
import type { Forecast } from "../types";
import { BandChart } from "./BandChart";

export function BandCard({ data }: { data: Forecast }) {
  const { band, price, currency } = data;
  const unit = currencyLabel(currency);
  const points = useMemo(() => buildChartData(data.history, band.horizon_days), [data.history, band.horizon_days]);
  const stats = outsideStats(points);
  const coverage = Math.round(band.coverage * 100);

  return (
    <section className="card" aria-labelledby="band-title">
      <h2 id="band-title" className="card__title">
        다음 {band.horizon_days}거래일 {coverage}% 가격 범위
      </h2>
      <p className="band__headline">
        <span className="band__range">
          {formatNumber(band.low)} ~ {formatNumber(band.high)} {unit}
        </span>{" "}
        <span className="band__width">(±{formatPct(halfWidth(band.low, band.high, price))})</span>
      </p>
      <p className="hint">
        기준가 {formatNumber(price, 2)} {unit}/{data.unit}. 과거 비슷한 상황에서 {band.horizon_days}거래일 뒤 가격이 약{" "}
        {coverage}% 확률로 이 안에 있었다는 뜻이에요. 방향을 알려주지는 않아요.
        {band.z_is_default && " (과거 오차 표본이 부족해 기본 배수 1.645를 썼어요)"}
      </p>

      <BandChart points={points} unit={unit} />

      <p className="hint">
        최근 {stats.checked}거래일 중 {stats.outside}일({stats.checked ? formatPct(stats.outside / stats.checked, 0) : "-"})이
        {" "}{band.horizon_days}거래일 전에 낸 범위를 벗어났어요.
      </p>

      <details className="table-view">
        <summary>최근 10거래일 표로 보기</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">날짜</th>
              <th scope="col">가격</th>
              <th scope="col">범위({band.horizon_days}거래일 전 예측)</th>
              <th scope="col">범위 안?</th>
            </tr>
          </thead>
          <tbody>
            {points.slice(-10).reverse().map((p) => (
              <tr key={p.date}>
                <td>{p.date}</td>
                <td>{p.price === null ? "-" : formatNumber(p.price, 2)}</td>
                <td>{p.low === null || p.high === null ? "-" : `${formatNumber(p.low)} ~ ${formatNumber(p.high)}`}</td>
                <td>{p.range === null ? "-" : p.outside === null ? "안" : "벗어남"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
