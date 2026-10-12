import { formatDate, formatPct } from "../format";
import type { Evaluation } from "../types";

export function ScoreCard({ evaluation }: { evaluation: Evaluation | null }) {
  return (
    <section className="card" aria-labelledby="score-title">
      <h2 id="score-title" className="card__title">
        모델 성적표
      </h2>
      {evaluation === null ? (
        <p className="hint">평가 결과가 아직 없어요. (python -m gold_service.evaluate 실행 후 다시 내보내 주세요)</p>
      ) : (
        <Score evaluation={evaluation} />
      )}
    </section>
  );
}

function Score({ evaluation: e }: { evaluation: Evaluation }) {
  const b = e.baseline;
  const target = Math.round(e.coverage_target * 100);
  const rows: [string, string, string][] = [
    [`${target}% 범위 적중률`, formatPct(e.hit_rate), formatPct(b.hit_rate)],
    ["평균 범위 폭", `±${formatPct(e.avg_width, 2)}`, `±${formatPct(b.avg_width, 2)}`],
    [`겹치지 않는 표본 적중률 (${e.n_nonoverlap}개)`, formatPct(e.hit_rate_nonoverlap), formatPct(b.hit_rate_nonoverlap)],
  ];
  return (
    <>
      <p className="score__period">
        테스트 기간 {formatDate(e.period_start)} ~ {formatDate(e.period_end)} · {e.n_days}거래일 (walk-forward)
      </p>
      <div className="table-scroll">
        <table className="score">
          <thead>
            <tr>
              <th scope="col">지표</th>
              <th scope="col">이 서비스 ({e.model_name})</th>
              <th scope="col">비교 기준 ({b.name})</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, model, base]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>{model}</td>
                <td>{base}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        범위를 넓히면 적중률은 저절로 올라가므로, 목표 {target}%에 얼마나 가까운지와 함께 범위 폭을 같이 봐야 해요.
      </p>
      <p className="hint">
        하루 변동성 예측 오차(QLIKE)는 단순 기준(최근 22일 변동성)보다 {formatPct(Math.abs(e.qlike_improvement))}{" "}
        {e.qlike_improvement >= 0 ? "작아요" : "커요"}. 겹치지 않는 표본은 5거래일 간격으로 뽑아 서로 기간이 겹치지 않는
        날만 센 값이에요.
      </p>
    </>
  );
}
