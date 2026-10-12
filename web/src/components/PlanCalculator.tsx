import { useId, useState } from "react";
import { formatWon } from "../format";
import { WEEKDAY_LABELS, buildPlan } from "../planner";
import type { GradeLabel } from "../types";

const PRODUCTS = ["KRX 금현물", "금 ETF", "골드뱅킹"] as const;
const DEFAULT_AMOUNT = 300_000;
const MAX_AMOUNT = 1_000_000_000;

interface Props {
  grade: GradeLabel;
  splitRule: Record<GradeLabel, number[]>;
}

export function parseAmount(text: string): number | null {
  const digits = text.replace(/[,\s원]/g, "");
  if (!/^\d+$/.test(digits)) return null;
  const n = Number(digits);
  return n > 0 && n <= MAX_AMOUNT ? n : null;
}

export function PlanCalculator({ grade, splitRule }: Props) {
  const amountId = useId();
  const productId = useId();
  const [amountText, setAmountText] = useState(DEFAULT_AMOUNT.toLocaleString("ko-KR"));
  const [product, setProduct] = useState<(typeof PRODUCTS)[number]>(PRODUCTS[0]);

  const amount = parseAmount(amountText);
  const items = amount === null ? [] : buildPlan(grade, amount, splitRule);
  const tooSmall = items.some((it) => it.amount === 0);

  return (
    <section className="card" aria-labelledby="plan-title">
      <h2 id="plan-title" className="card__title">
        분할 플랜 계산기
      </h2>
      <form className="plan__form" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor={amountId}>
          주간 매수 금액(원)
          <input
            id={amountId}
            inputMode="numeric"
            autoComplete="off"
            value={amountText}
            onChange={(e) => setAmountText(e.target.value)}
            onBlur={() => amount !== null && setAmountText(amount.toLocaleString("ko-KR"))}
            aria-invalid={amount === null}
            aria-describedby={`${amountId}-err`}
          />
        </label>
        <label htmlFor={productId}>
          매수 상품
          <select id={productId} value={product} onChange={(e) => setProduct(e.target.value as typeof product)}>
            {PRODUCTS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
      </form>
      <p id={`${amountId}-err`} className="field-error" aria-live="polite">
        {amount === null ? "1원 이상 10억 원 이하의 숫자로 입력해 주세요." : ""}
      </p>

      {amount !== null && (
        <div className="plan__result" aria-live="polite">
          <p className="plan__summary">
            이번 주 변동성 <strong>{grade}</strong> → <strong>{items.length}회</strong>로 나눠서
            <span className="plan__product"> · {product}</span>
          </p>
          <ol className="plan__items">
            {items.map((it) => (
              <li key={it.seq}>
                <span className="plan__seq">{it.seq}회차</span>
                <span className="plan__day">{WEEKDAY_LABELS[it.tradeWeekday]}요일</span>
                <span className="plan__amount">{formatWon(it.amount)}</span>
              </li>
            ))}
          </ol>
          {tooSmall && <p className="notice">금액이 분할 횟수보다 작아 0원인 회차가 있어요.</p>}
          <p className="hint">
            휴장일 정보는 반영하지 않았어요. 계획한 요일이 휴장이면 그 주의 다음 거래일로 미뤄요. 회차 금액은 원 단위로
            나누고 나머지는 마지막 회차에 더해요. 매수 상품 선택은 표시용이며 계산은 같아요.
          </p>
        </div>
      )}
    </section>
  );
}
