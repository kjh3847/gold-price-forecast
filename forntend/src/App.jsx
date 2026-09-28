import { useEffect, useState } from 'react';
import { Coins, TrendingUp, Sparkles, Layers, CalendarDays, Info, ArrowUpRight } from 'lucide-react';
import Layout, { navigation } from './components/Layout.jsx';
import StatCard from './components/StatCard.jsx';
import GoldPriceChart from './components/GoldPriceChart.jsx';
import PredictionCard from './components/PredictionCard.jsx';
import ModelMetrics from './components/ModelMetrics.jsx';
import PriceTable from './components/PriceTable.jsx';
import SavedPredictions from './components/SavedPredictions.jsx';
import * as goldService from './services/goldService.js';
import { money, signed, dateLabel } from './utils/format.js';

const pageDescriptions = {
  dashboard: ['시장의 흐름, 데이터로 한눈에.', '금 시세와 예측 결과를 한곳에서 확인하세요.'],
  prices: ['금 시세 분석', '기간별 가격 흐름과 실제값·예측값을 비교하세요.'],
  prediction: ['금 가격 예측', '예측 날짜별 결과를 확인하고 기록을 저장하세요.'],
  performance: ['모델 성능 검증', '실제값과 예측값의 차이를 살펴보고 모델의 성능을 확인하세요.'],
  data: ['데이터 조회', '날짜별 금 시세와 저장한 예측 결과를 확인하세요.'],
};
const readPage = () => navigation.some((item) => item.id === location.hash.slice(1)) ? location.hash.slice(1) : 'dashboard';

export default function App() {
  const [page, setPage] = useState(readPage);
  const [dashboard, setDashboard] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [predictionOptions, setPredictionOptions] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [rows, setRows] = useState([]);
  const [saved, setSaved] = useState([]);
  const [period, setPeriod] = useState('3M');
  const [compare, setCompare] = useState(true);
  const [error, setError] = useState('');
  const [storageError, setStorageError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const handler = () => setPage(readPage());
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);
  useEffect(() => {
    let active = true;
    Promise.all([goldService.getDashboard(), goldService.getPrediction(), goldService.getModelEvaluation(), goldService.getPredictionOptions()]).then(([summary, forecast, metrics, options]) => { if (active) { setDashboard(summary); setPrediction(forecast); setEvaluation(metrics); setPredictionOptions(options); } }).catch(() => { if (active) setError('데이터를 불러오지 못했습니다. 페이지를 새로고침해주세요.'); });
    goldService.getSavedPredictions().then((data) => { if (active) setSaved(data); }).catch((err) => { if (active) setStorageError(err.message); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    goldService.getPrices({ period }).then((data) => { if (active) setRows(data); }).catch(() => { if (active) setError('차트 데이터를 불러오지 못했습니다.'); });
    return () => { active = false; };
  }, [period]);
  function navigate(next) { location.hash = next; setPage(next); window.scrollTo({ top: 0 }); }
  async function changeDate(date) {
    setBusy(true); setMessage('');
    try { setPrediction(await goldService.getPrediction(date)); }
    catch (err) { setMessage(err.message); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true);
    try { const result = await goldService.savePrediction(prediction); setSaved(result.rows); setStorageError(''); setMessage(result.duplicate ? '이미 저장한 예측 결과입니다.' : '이 브라우저에 예측 결과를 저장했습니다.'); }
    catch (err) { setMessage(err.message); }
    finally { setBusy(false); }
  }
  if (!dashboard || !prediction || !evaluation) return <Layout page={page} onNavigate={navigate}><div className="loading-state" role={error ? 'alert' : 'status'}>{error || '대시보드를 준비하고 있습니다…'}</div></Layout>;
  const change = dashboard.current.close - dashboard.previous.close;
  const changePercent = change / dashboard.previous.close * 100;
  const forecastCard = <PredictionCard prediction={prediction} options={predictionOptions} onDateChange={changeDate} onSave={save} busy={busy} message={message} />;
  const chart = <GoldPriceChart rows={rows} period={period} onPeriodChange={setPeriod} compare={compare} onCompareChange={setCompare} />;
  return <Layout page={page} onNavigate={navigate}>
    <div className="page-heading"><div><div className="eyebrow">GOLD PRICE FORECAST <span>/ {page === 'dashboard' ? 'OVERVIEW' : page.toUpperCase()}</span></div><h1>{pageDescriptions[page][0]}</h1><p>{pageDescriptions[page][1]}</p></div><div className="as-of"><CalendarDays size={16} /><span>{dateLabel(dashboard.asOf)} 기준</span></div></div>
    <div className="demo-notice"><Info size={17} /><span>현재 <strong>데이터 수집 단계이며 모델은 학습하지 않았습니다.</strong> 가격과 예측은 UI 확인을 위해 임의로 만든 예시입니다.</span><span className="notice-tag">DEMO MODE</span></div>
    {error && <p role="alert" className="inline-error">{error}</p>}{storageError && <p role="alert" className="inline-error">{storageError}</p>}
    {(page === 'dashboard' || page === 'prices') && <div className="stats-grid"><StatCard label="현재 금 시세" value={money(dashboard.current.close)} unit="/ g" change={changePercent} detail="전일 대비" icon={Coins} accent /><StatCard label="전일 대비 변동" value={`${signed(change)}원`} change={changePercent} detail="일별 종가 기준" icon={TrendingUp} /><StatCard label={prediction.source === 'mock' ? '예측 가격 (임의 예시)' : '머신러닝 예측 가격'} value={money(prediction.predictedPrice)} unit="/ g" detail={`${dateLabel(prediction.date)} · mock 예측`} icon={Sparkles} /><StatCard label="예측 모델" value="모델 미학습" detail="현재 데이터 수집 단계" icon={Layers} /></div>}
    {page === 'dashboard' && <><div className="dashboard-grid">{chart}{forecastCard}</div><ModelMetrics evaluation={evaluation} onNavigate={() => navigate('performance')} /><PriceTable compact onNavigate={() => navigate('data')} /></>}
    {page === 'prices' && <>{chart}<PriceTable compact onNavigate={() => navigate('data')} /></>}
    {page === 'prediction' && <div className="prediction-page-grid">{forecastCard}<div className="stack"><section className="prediction-explainer panel"><span className="tiny-label">FORECAST INSIGHT</span><h2>과거의 흐름에서<br />다음 가격을 바라봅니다.</h2><p>기준일의 금 가격을 바탕으로 선택한 날짜의 예상 가격과 변동률을 확인할 수 있습니다.</p><div className="prediction-flow"><span>과거 금 시세</span><ArrowUpRight size={18} /><span>임시 계산</span><ArrowUpRight size={18} /><span>가격 예측</span></div><div className="training-note"><Info size={17} /><span>현재는 고정된 시연용 계산 결과입니다.<br />머신러닝 모델은 데이터 분석 후 선정될 예정입니다.</span></div></section><SavedPredictions rows={saved} /></div></div>}
    {page === 'performance' && <><ModelMetrics evaluation={evaluation} /><GoldPriceChart rows={evaluation.rows} compare title="실제값 vs 예측값" subtitle="최근 30일 비교 예시 · 두 계열 모두 mock 데이터이며, 모델 검증 결과가 아닙니다." id="evaluation" /><section className="panel validation-note"><h2>모델 검증 준비</h2><p>모델 학습 후 학습에 사용하지 않은 테스트 데이터의 평가 결과가 표시됩니다. Linear Regression, Random Forest, XGBoost, LSTM 등을 검토하며, 아직 최종 모델은 정해지지 않았습니다.</p></section></>}
    {page === 'data' && <><PriceTable /><SavedPredictions rows={saved} /></>}
  </Layout>;
}
