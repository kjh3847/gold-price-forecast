/**
 * Shared boundary for mock fixtures and future backend prediction responses.
 * @typedef {Object} PredictionResponse
 * @property {string} id Server-generated prediction identity
 * @property {string} asOf Data cutoff date (YYYY-MM-DD)
 * @property {string} date Target date (YYYY-MM-DD)
 * @property {number} currentPrice Positive reference price
 * @property {number} predictedPrice Positive forecast price
 * @property {string} model Model display name
 * @property {string} modelVersion Model version (demo-v1 for mock)
 * @property {'mock'|'model'} source Whether ML inference was actually used
 * @property {'KRW/g'} unit Backend must convert to the UI's price unit
 */
function validDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && !Number.isNaN(Date.parse(value))
    && new Date(value).toISOString().slice(0, 10) === value;
}

/** @param {PredictionResponse} response */
export function normalizePrediction(response) {
  if (!response || !['id', 'model', 'modelVersion'].every((key) => typeof response[key] === 'string' && response[key].trim())
      || !validDate(response.asOf) || !validDate(response.date) || response.date <= response.asOf
      || !Number.isFinite(response.currentPrice) || response.currentPrice <= 0
      || !Number.isFinite(response.predictedPrice) || response.predictedPrice <= 0
      || !['mock', 'model'].includes(response.source) || response.unit !== 'KRW/g') {
    throw new Error('예측 응답의 날짜·가격·단위·모델 정보를 확인해주세요.');
  }
  return {
    ...response,
    change: response.predictedPrice - response.currentPrice,
    changePercent: (response.predictedPrice / response.currentPrice - 1) * 100,
  };
}
