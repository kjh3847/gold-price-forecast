import { FlaskConical, ArrowUpRight } from 'lucide-react';
const labels = { MAE: '평균 절대 오차', RMSE: '평균 제곱근 오차', MAPE: '평균 절대 백분율 오차', 'R²': '결정계수' };
export default function ModelMetrics({ evaluation, onNavigate }) {
  return <section className="panel metrics-panel"><div className="panel-heading"><div><h2>모델 성능</h2><p>테스트 데이터 기반 모델 평가 지표</p></div>{onNavigate && <button className="text-button" onClick={onNavigate}>자세히 보기<ArrowUpRight size={16} /></button>}</div><div className="metrics-grid">{Object.entries(evaluation.metrics).map(([key, value]) => <div className="metric" key={key}><span>{key}</span><strong>{value ?? '—'}</strong><small>{labels[key]}</small></div>)}</div><div className="training-note"><FlaskConical size={16} /><span>모델 학습 후 표시 예정 <span className="training-detail">· 모델 선정 및 검증을 준비하고 있습니다.</span></span><span className="pending-dot" /></div></section>;
}
