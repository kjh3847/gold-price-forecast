import { ArrowUpRight, ArrowDownRight, BookmarkPlus, Sparkles } from 'lucide-react';
import { money, signed, dateLabel } from '../utils/format.js';

export default function PredictionCard({ prediction, options, onDateChange, onSave, busy, message }) {
  const isMock = prediction.source === 'mock';
  const rising = prediction.change >= 0;
  const direction = prediction.change === 0 ? '보합' : rising ? '상승' : '하락';
  const Arrow = rising ? ArrowUpRight : ArrowDownRight;
  return <section className="panel prediction-panel"><div className="panel-heading"><h2><Sparkles size={18} />금 가격 예측</h2><span className="soft-badge">{isMock ? '임의 예시' : '모델 예측'}</span></div><p className="prediction-intro">{isMock ? '데이터 수집 단계 · 모델 미학습 상태입니다.' : `${prediction.model} · ${prediction.modelVersion}`}</p><label className="field-label" htmlFor="prediction-date">예측 날짜</label><select id="prediction-date" value={prediction.date} disabled={busy} onChange={(e) => onDateChange(e.target.value)}>{options.map(({ date, days }) => <option key={date} value={date}>{dateLabel(date)} · {days === 1 ? '다음 날' : `${days}일 후`}</option>)}</select>
    <div className="forecast-value"><span>예측 가격 <small>KRW / g</small></span><strong>{money(prediction.predictedPrice)}</strong><div className={`direction-badge ${rising ? 'positive' : 'negative'}`}>{prediction.change !== 0 && <Arrow size={15} />}{direction} 예상 · {signed(prediction.changePercent, 2)}%</div></div>
    <dl className="prediction-details"><div><dt>현재 가격</dt><dd>{money(prediction.currentPrice)}</dd></div><div><dt>예상 변동액</dt><dd className={rising ? 'positive' : 'negative'}>{signed(prediction.change)}원</dd></div><div><dt>예측 기준일</dt><dd>{dateLabel(prediction.asOf)}</dd></div><div><dt>모델</dt><dd>{prediction.model}</dd></div></dl>
    <button className="primary-button" disabled={busy} onClick={onSave}><BookmarkPlus size={17} />{busy ? '처리 중…' : '예측 결과 저장'}</button><p className="storage-hint">이 브라우저에 임시 저장됩니다.</p>{message && <p role="status" className="save-message">{message}</p>}
  </section>;
}
