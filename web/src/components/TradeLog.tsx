import { useState, type FormEvent } from "react";
import { formatNumber, formatWon } from "../format";
import { WEEKDAY_LABELS } from "../planner";

export interface PlanSnapshot {
  policy_version: string | null;
  n_splits: number;
  items: { seq: number; weekday: number; amount: number }[];
}

export interface TradeRecord {
  seq: number;
  trade_date: string;
  price: number;
  amount: number;
}

export interface TradeSummary {
  n_splits: number | null;
  done: number;
  total_amount: number;
  avg_cost: number | null;
}

interface Props {
  plan: PlanSnapshot | undefined;
  trades: TradeRecord[];
  summary: TradeSummary | undefined;
  unit: string;
  busy: boolean;
  onSave: (seq: number, tradeDate: string, price: number) => void;
}

function TradeRow({ item, trade, unit, busy, onSave }: {
  item: PlanSnapshot["items"][number];
  trade: TradeRecord | undefined;
  unit: string;
  busy: boolean;
  onSave: Props["onSave"];
}) {
  const [date, setDate] = useState(trade?.trade_date ?? "");
  const [price, setPrice] = useState(trade ? String(trade.price) : "");

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = Number(price);
    if (!date || !Number.isFinite(value) || value <= 0) return;
    onSave(item.seq, date, value);
  }

  return (
    <li className={`trade ${trade ? "trade--done" : ""}`}>
      <div className="trade__head">
        <span className="plan__seq">{item.seq}회차</span>
        <span className="plan__day">{WEEKDAY_LABELS[item.weekday]}요일 계획</span>
        <span className="plan__amount">{formatWon(item.amount)}</span>
        <span className="trade__status">{trade ? "✓ 기록됨" : "미기록"}</span>
      </div>
      <form className="trade__form" onSubmit={submit}>
        <label>
          체결일
          <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>
          체결 단가 ({unit})
          <input type="number" required min="0.000001" step="any" inputMode="decimal" value={price}
                 onChange={(e) => setPrice(e.target.value)} />
        </label>
        <button disabled={busy}>{trade ? "수정" : "기록"}</button>
      </form>
    </li>
  );
}

/** 저장된 플랜의 회차별 실제 매수 기록과 평균 단가. */
export function TradeLog({ plan, trades, summary, unit, busy, onSave }: Props) {
  if (!plan) {
    return <p className="hint">이 접수에는 분할 플랜이 없어요. 입력값을 새로 저장하면 매수 기록을 남길 수 있어요.</p>;
  }
  const bySeq = new Map(trades.map((t) => [t.seq, t]));
  return (
    <div className="trades" aria-label="내 매수 기록">
      <h3>내 매수 기록</h3>
      <p className="hint">
        저장한 플랜({plan.n_splits}회 분할{plan.policy_version ? ` · ${plan.policy_version}` : ""})대로 실제로 산 날짜와 단가를
        기록하세요. 기록은 분할 규칙을 다시 학습하는 데 쓰여요.
      </p>
      <ol className="trades__list">
        {plan.items.map((item) => (
          <TradeRow key={`${item.seq}-${bySeq.get(item.seq)?.trade_date ?? ""}`} item={item} trade={bySeq.get(item.seq)}
                    unit={unit} busy={busy} onSave={onSave} />
        ))}
      </ol>
      {summary && summary.done > 0 && (
        <p className="trades__summary" role="status">
          {summary.done}/{summary.n_splits ?? plan.n_splits}회 기록 · 누적 {formatWon(summary.total_amount)}
          {summary.avg_cost !== null && <> · 평균 매수 단가 <strong>{formatNumber(summary.avg_cost, 2)} {unit}</strong></>}
        </p>
      )}
    </div>
  );
}
