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
  volatility_projection?: { date: string; horizon_day: number; cumulative_sigma_pct: number }[];
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
  policy?: PolicyInfo | null;
  model?: ModelInfo | null;
}

export interface GradeSimulation {
  weeks: number;
  n_splits: number;
  timing_error: number;
  lump_timing_error: number;
}

// 분할 규칙 과거 시뮬레이션 (타이밍 오차 = |평균 매수 단가 / 그 주 평균 종가 − 1|)
export interface Simulation {
  weeks: number;
  period_start: string;
  period_end: string;
  cost_per_trade: number;
  avg_trades: number;
  timing_error: number;
  timing_error_worst: number;
  lump_timing_error: number;
  lump_timing_error_worst: number;
  daily_timing_error: number;
  cheaper_than_lump_share: number;
  reward: number;
  by_grade: Partial<Record<GradeLabel, GradeSimulation>>;
}

export interface PolicyTraining {
  trained_at: string;
  holdout_weeks: number;
  holdout_start: string;
  holdout_reward_current: number | null;
  holdout_reward_candidate: number | null;
  log_samples: number;
  current_rule: Record<string, number[]>;
  candidate_rule: Record<string, number[]>;
  accepted: boolean;
  reason: string;
  previous_version?: string | null;
}

export interface PolicyInfo {
  version: string;
  source: "default" | "trained";
  activated_at: string | null;
  cost_per_trade: number;
  simulation: Simulation | null;
  training: PolicyTraining | null;
  previous_version: string | null;
}

export interface ModelInfo {
  version: string;
  trained_on: string;
  last_train_row: string;
  n_train_rows: number;
  name: string;
}
