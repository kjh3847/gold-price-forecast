import { AS_OF, MODEL, prices } from './mockGold.js';

// UI-only scenarios. No training, statistical inference, or ML model is used.
export const mockPredictionOptions = [1, 7, 30].map((days) => {
  const date = new Date(`${AS_OF}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return { days, date: date.toISOString().slice(0, 10) };
});

export const mockPredictions = mockPredictionOptions.map(({ days, date }) => ({
  id: `${AS_OF}:${date}:${MODEL.version}`,
  asOf: AS_OF,
  date,
  currentPrice: prices.at(-1).close,
  predictedPrice: Math.round(prices.at(-1).close * (1 + days * 0.00085 + 0.003)),
  model: MODEL.name,
  modelVersion: MODEL.version,
  source: 'mock',
  unit: 'KRW/g',
}));
