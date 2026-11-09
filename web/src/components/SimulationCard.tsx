import { formatDate, formatPct } from "../format";
import { WEEKDAY_LABELS } from "../planner";
import { GRADES, type PolicyInfo } from "../types";

const GRADE_KEYS: Record<string, string> = { LOW: "낮음", NORMAL: "보통", HIGH: "높음", VERY_HIGH: "매우 높음" };

function ruleText(rule: Record<string, number[]>): string {
  return Object.entries(rule)
    .map(([key, days]) => `${GRADE_KEYS[key] ?? key} ${days.length}회`)
    .join(" · ");
}

export function policyLabel(policy: PolicyInfo | null | undefined): string {
  if (!policy) return "기본 규칙";
  return `${policy.source === "trained" ? "학습된 규칙" : "기본 규칙"} (${policy.version})`;
}

/** 분할 규칙을 과거에 그대로 적용했을 때의 결과와 학습 이력. */
export function SimulationCard({ policy }: { policy: PolicyInfo | null | undefined }) {
  const sim = policy?.simulation;
  return (
    <section className="card" aria-labelledby="sim-title">
      <h2 id="sim-title" className="card__title">
        과거 성과 시뮬레이션
      </h2>
      {!sim || !sim.weeks ? (
        <p className="hint">시뮬레이션 결과가 아직 없어요. (배치 실행 시 자동으로 계산돼요)</p>
      ) : (
        <>
          <p className="sim__headline">
            지난 {sim.weeks}주 동안 이 규칙대로 나눠 샀다면, 매수 단가가 그 주 평균 가격에서 벗어난 정도가
            <strong> 평균 {formatPct(sim.lump_timing_error, 2)} → {formatPct(sim.timing_error, 2)}</strong>로 줄었어요.
          </p>
          <p className="hint">
            {formatDate(sim.period_start)} ~ {formatDate(sim.period_end)} · 적용 규칙: {policyLabel(policy)}
          </p>
          <div className="table-scroll">
            <table className="score">
              <thead>
                <tr>
                  <th scope="col">매수 방식</th>
                  <th scope="col">평균 타이밍 오차</th>
                  <th scope="col">가장 나빴던 주</th>
                  <th scope="col">주당 매수 횟수</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">이 서비스 규칙</th>
                  <td>{formatPct(sim.timing_error, 2)}</td>
                  <td>{formatPct(sim.timing_error_worst, 2)}</td>
                  <td>{sim.avg_trades.toFixed(1)}회</td>
                </tr>
                <tr>
                  <th scope="row">월요일에 한 번에</th>
                  <td>{formatPct(sim.lump_timing_error, 2)}</td>
                  <td>{formatPct(sim.lump_timing_error_worst, 2)}</td>
                  <td>1회</td>
                </tr>
                <tr>
                  <th scope="row">매일 나눠서</th>
                  <td>{formatPct(sim.daily_timing_error, 2)}</td>
                  <td>-</td>
                  <td>5회</td>
                </tr>
              </tbody>
            </table>
          </div>

          <details className="table-view">
            <summary>등급별로 보기</summary>
            <table>
              <thead>
                <tr>
                  <th scope="col">등급</th>
                  <th scope="col">주 수</th>
                  <th scope="col">분할</th>
                  <th scope="col">이 규칙</th>
                  <th scope="col">한 번에</th>
                </tr>
              </thead>
              <tbody>
                {GRADES.filter((g) => sim.by_grade[g]).map((g) => {
                  const row = sim.by_grade[g]!;
                  return (
                    <tr key={g}>
                      <td>{g}</td>
                      <td>{row.weeks}</td>
                      <td>{row.n_splits}회</td>
                      <td>{formatPct(row.timing_error, 2)}</td>
                      <td>{formatPct(row.lump_timing_error, 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
          <p className="hint">
            타이밍 오차 = |실제 평균 매수 단가 ÷ 그 주 평균 종가 − 1|. 금값 방향과 무관하게 "운 나쁜 날 한 번에 사는 위험"을
            얼마나 줄였는지를 봐요. 분할로 평균 단가가 꼭 낮아지는 것은 아니에요(한 번에 산 것보다 싸게 산 주{" "}
            {formatPct(sim.cheaper_than_lump_share, 0)}).
          </p>
        </>
      )}

      {policy?.training && (
        <div className="sim__training">
          <h3>규칙 학습 이력</h3>
          <p>
            {formatDate(policy.training.trained_at.slice(0, 10))} 학습 · 과거 데이터 + 사용자 매수 기록{" "}
            {policy.training.log_samples}건 · 최근 {policy.training.holdout_weeks}주로 검증
          </p>
          <p>
            이전: {ruleText(policy.training.current_rule)}
            <br />
            현재: {ruleText(policy.training.candidate_rule)}
          </p>
          <p className="hint">
            {policy.training.reason}. 점수는 −(타이밍 오차 + 회차당 부담 {formatPct(policy.cost_per_trade, 1)} × 추가 회차)로,
            많이 나눌수록 오차는 줄지만 수수료·번거로움이 늘어나는 균형을 봐요.
          </p>
        </div>
      )}
      <p className="hint">요일: {WEEKDAY_LABELS.join("·")} 기준. 과거 결과가 앞으로의 결과를 보장하지 않아요.</p>
    </section>
  );
}
