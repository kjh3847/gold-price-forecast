import test from 'node:test';
import assert from 'node:assert/strict';
import * as service from '../src/services/goldService.js';
import { normalizePrediction } from '../src/services/predictionContract.js';

test('periods and inclusive date filters return ordered, valid OHLC observations', async () => {
  for (const [period, count] of Object.entries(service.periods)) {
    const rows = await service.getPrices({ period });
    assert.equal(rows.length, count);
    for (const row of rows) {
      assert.ok(row.high >= Math.max(row.open, row.close));
      assert.ok(row.low <= Math.min(row.open, row.close));
    }
    assert.deepEqual(rows.map((row) => row.date), rows.map((row) => row.date).sort());
  }
  const rows = await service.getPrices({ period: '1Y', start: '2026-09-01', end: '2026-09-03' });
  assert.deepEqual(rows.map((row) => row.date), ['2026-09-01', '2026-09-02', '2026-09-03']);
  assert.equal((await service.getPrices({ start: '2030-01-01' })).length, 0);
});
test('predictions are consistent, explicitly mock, and reject unsupported dates', async () => {
  for (const option of await service.getPredictionOptions()) {
    const result = await service.getPrediction(option.date);
    assert.equal(result.date, option.date);
    assert.equal(result.change, result.predictedPrice - result.currentPrice);
    assert.equal(result.source, 'mock');
  }
  await assert.rejects(service.getPrediction('2030-01-01'));
  assert.ok(Object.values((await service.getModelEvaluation()).metrics).every((value) => value === null));
});
test('saved forecasts survive reads, deduplicate, and report storage failures', async () => {
  const store = new Map();
  globalThis.localStorage = { getItem: (key) => store.get(key) ?? null, setItem: (key, value) => store.set(key, value) };
  const prediction = await service.getPrediction();
  assert.equal((await service.savePrediction(prediction)).duplicate, false);
  assert.equal((await service.savePrediction(prediction)).duplicate, true);
  assert.equal((await service.getSavedPredictions()).length, 1);
  globalThis.localStorage.setItem = () => { throw new Error('QuotaExceededError'); };
  const options = await service.getPredictionOptions();
  await assert.rejects(service.savePrediction(await service.getPrediction(options[1].date)), /저장/);
  globalThis.localStorage.getItem = () => 'broken-json';
  await assert.rejects(service.getSavedPredictions(), /읽을 수 없습니다/);
});

test('future model responses support new dates and falling or flat prices through the same contract', () => {
  const response = {
    id: 'server-prediction-1', asOf: '2027-01-01', date: '2027-02-15',
    currentPrice: 160000, predictedPrice: 156000, source: 'model',
    model: 'Example trained model', modelVersion: 'v1', unit: 'KRW/g',
  };
  assert.equal(normalizePrediction(response).change, -4000);
  assert.ok(Math.abs(normalizePrediction(response).changePercent + 2.5) < 1e-10);
  assert.equal(normalizePrediction({ ...response, predictedPrice: 160000 }).change, 0);
  for (const invalid of [{ unit: 'USD/oz' }, { currentPrice: 0 }, { predictedPrice: null }, { predictedPrice: NaN }, { date: '2027-02-30' }, { modelVersion: '' }]) {
    assert.throws(() => normalizePrediction({ ...response, ...invalid }), /예측 응답/);
  }
});
