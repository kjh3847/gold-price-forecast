// Fixed, reproducible demo fixture; KRW per gram. Not market or trained model data.
export const AS_OF = '2026-09-28';
export const MODEL = { name: '모델 선정 예정', version: 'demo-v1', trained: false };
export const prices = Array.from({ length: 365 }, (_, i) => {
  const date = new Date(`${AS_OF}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 364 + i);
  const close = Math.round(128000 + i * 79 + Math.sin(i / 18) * 3100 + Math.sin(i / 4.3) * 740);
  const open = Math.round(close - Math.sin(i * 1.7) * 480);
  return {
    date: date.toISOString().slice(0, 10), open,
    high: Math.max(open, close) + 530 + (i % 7) * 40,
    low: Math.min(open, close) - 430 - (i % 5) * 35,
    close, predicted: Math.round(close + Math.sin(i / 5) * 640 + 190),
  };
});
