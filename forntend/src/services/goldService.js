import { AS_OF, MODEL, prices } from '../data/mockGold.js';
import { mockPredictionOptions, mockPredictions } from '../data/mockPredictions.js';
import { normalizePrediction } from './predictionContract.js';

const STORAGE_KEY = 'gold-forecast.saved.v1';
export const periods = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365 };
export async function getPredictionOptions() {
  return mockPredictionOptions.map((option) => ({ ...option }));
}

// Async interface: replace method bodies with API calls when the backend is ready.
// SQLite and the trained model belong behind the backend, never inside React.
export async function getDashboard() {
  return { asOf: AS_OF, current: prices.at(-1), previous: prices.at(-2), model: MODEL, source: 'mock' };
}
export async function getPrices({ period = '3M', start = '', end = '' } = {}) {
  return prices.slice(-periods[period]).filter((row) => (!start || row.date >= start) && (!end || row.date <= end));
}
export async function getPrediction(date) {
  // Later: fetch a backend prediction here, then pass it to normalizePrediction.
  // Keep the mock-only formula in data/, outside the API contract and components.
  const response = date ? mockPredictions.find((item) => item.date === date) : mockPredictions[0];
  if (!response) throw new Error('지원하지 않는 예측 날짜입니다.');
  return normalizePrediction(response);
}
export async function getModelEvaluation() {
  return { model: MODEL, metrics: { MAE: null, RMSE: null, MAPE: null, 'R²': null }, rows: prices.slice(-30), source: 'mock' };
}
export async function getSavedPredictions() {
  try {
    const rows = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(rows) || rows.some((row) => !row || typeof row.id !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(row.date) || !/^\d{4}-\d{2}-\d{2}$/.test(row.asOf) || !Number.isFinite(row.predictedPrice))) {
      throw new Error('invalid storage');
    }
    return rows;
  } catch {
    throw new Error('브라우저 저장 내역을 읽을 수 없습니다. 브라우저 저장소 설정을 확인해주세요.');
  }
}
export async function savePrediction(prediction) {
  const rows = await getSavedPredictions();
  if (rows.some((row) => row.id === prediction.id)) return { rows, duplicate: true };
  const next = [{ ...prediction, savedAt: new Date().toISOString() }, ...rows];
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); }
  catch { throw new Error('저장 공간이 부족하거나 브라우저 저장이 차단되어 있습니다.'); }
  return { rows: next, duplicate: false };
}
