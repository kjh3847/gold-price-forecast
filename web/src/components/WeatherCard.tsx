import { GRADE_META, explainPercentile, formatPct } from "../format";
import type { Forecast } from "../types";

export function WeatherCard({ data }: { data: Forecast }) {
  const meta = GRADE_META[data.grade];
  return (
    <section className="card weather" aria-labelledby="weather-title">
      <h2 id="weather-title" className="card__title">
        이번 주 변동성 날씨
      </h2>
      <div className="weather__body">
        <div className={`grade grade--${meta.tone}`}>
          <span className="grade__icon" aria-hidden="true">
            {meta.icon}
          </span>
          <div>
            <p className="grade__label">
              변동성 <strong>{data.grade}</strong>
            </p>
            <p className="grade__weather">{meta.weather}</p>
          </div>
        </div>
        <dl className="stats">
          <div>
            <dt>하루 예상 움직임</dt>
            <dd className="stats__value">±{formatPct(data.sigma_daily, 2)}</dd>
          </div>
          <div>
            <dt>최근 252일 중 백분위</dt>
            <dd className="stats__value">{data.percentile === null ? "-" : formatPct(data.percentile, 0)}</dd>
          </div>
        </dl>
      </div>
      <p className="weather__explain">{explainPercentile(data.grade, data.percentile)}</p>
      {data.is_fallback && (
        <p className="notice" role="note">
          ⚠️ 오늘은 모델 대신 최근 변동성(최근 22일)으로 계산했어요.
        </p>
      )}
      <p className="hint">변동성은 금값이 얼마나 출렁일지에 대한 추정이며, 오를지 내릴지는 예측하지 않아요.</p>
    </section>
  );
}
