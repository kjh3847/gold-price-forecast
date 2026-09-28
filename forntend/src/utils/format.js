export const number = (value) => new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(value);
export const money = (value) => `₩${number(value)}`;
export const signed = (value, digits = 0) => `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR', { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
export const dateLabel = (value) => value.replaceAll('-', '.');
