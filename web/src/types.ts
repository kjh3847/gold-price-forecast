// forecast.json 스키마 (Python gold_service.export_json 과 키 이름이 같아야 한다)

export type GradeLabel = "낮음" | "보통" | "높음" | "매우 높음";

export const GRADES: GradeLabel[] = ["낮음", "보통", "높음", "매우 높음"];

export interface HistoryPoint {
  date: string;
  price: number | null;
  sigma_daily: number | null;
  grade: GradeLabel | null;
  band_low: number | null; // 이 날짜 종가 기준으로 낸 다음 5거래일 범위
  band_high: number | null;
}

export interface BandMetrics {
  hit_rate: number; // 0~1
  avg_width: number; // 범위 반폭 비율, 0.046 = ±4.6%
  hit_rate_nonoverlap: number;
  n_nonoverlap: number;
}

export interface Evaluation extends BandMetrics {
  model_name: string;
  period_start: string;
  period_end: string;
  n_days: number;
  coverage_target: number;
  qlike_improvement: number;
  fallback_days: number;
  baseline: BandMetrics & { name: string };
}

export interface Forecast {
  generated_at: string;
  as_of: string;
  currency: string;
  unit: string;
  price: number;
  sigma_daily: number;
  grade: GradeLabel;
  percentile: number | null; // 0~1
  is_fallback: boolean;
  band: {
    horizon_days: number;
    coverage: number;
    z: number;
    z_is_default?: boolean;
    low: number;
    high: number;
  };
  history: HistoryPoint[];
  evaluation: Evaluation | null;
  split_rule: Record<GradeLabel, number[]>;
}
