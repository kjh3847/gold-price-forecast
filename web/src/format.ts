import type { GradeLabel } from "./types";

const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];

export function formatNumber(value: number, digits = 0): string {
  return value.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatWon(value: number): string {
  return `${formatNumber(Math.round(value))}원`;
}

export function formatPct(ratio: number, digits = 1): string {
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** "2026-09-24" → "2026년 9월 24일 (목)" */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const day = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return `${y}년 ${m}월 ${d}일 (${DAY_NAMES[day]})`;
}

/** "2026-09-24" → "26.09" */
export function formatMonthTick(iso: string): string {
  return `${iso.slice(2, 4)}.${iso.slice(5, 7)}`;
}

/** ISO 시각 → 한국 시간 "2026. 10. 12. 오후 5:35" */
export function formatDateTimeKst(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function currencyLabel(currency: string): string {
  return currency === "USD" ? "달러" : currency === "KRW" ? "원" : currency;
}

/** 범위 반폭 비율 = (상한 − 하한) / (2 × 기준가) */
export function halfWidth(low: number, high: number, price: number): number {
  return (high - low) / (2 * price);
}

export interface GradeMeta {
  icon: string;
  weather: string;
  tone: "calm" | "mild" | "rough" | "storm";
}

export const GRADE_META: Record<GradeLabel, GradeMeta> = {
  낮음: { icon: "☀️", weather: "맑음", tone: "calm" },
  보통: { icon: "⛅", weather: "구름 조금", tone: "mild" },
  높음: { icon: "🌧️", weather: "비", tone: "rough" },
  "매우 높음": { icon: "⛈️", weather: "폭풍우", tone: "storm" },
};

/** 백분위(0~1)를 한 줄 해설로 바꾼다. 방향(상승·하락) 표현은 쓰지 않는다. */
export function explainPercentile(grade: GradeLabel, percentile: number | null): string {
  if (percentile === null) return "비교할 과거 예측이 아직 충분하지 않아요.";
  const lower = Math.max(1, Math.round(percentile * 100));
  const upper = Math.max(1, Math.round((1 - percentile) * 100));
  switch (grade) {
    case "낮음":
      return `최근 1년 중 하위 ${lower}% 수준으로 출렁임이 작은 편이에요.`;
    case "보통":
      return `최근 1년 중 중간 정도(하위 ${lower}%)의 출렁임이에요.`;
    case "높음":
      return `최근 1년 중 상위 ${upper}% 수준으로 출렁임이 큰 편이에요.`;
    case "매우 높음":
      return `최근 1년 중 상위 ${upper}% 수준으로 출렁임이 매우 큰 편이에요.`;
  }
}
