import { useState, type FormEvent } from "react";
import type { Forecast } from "../types";
import { TradeLog, type PlanSnapshot, type TradeRecord, type TradeSummary } from "./TradeLog";

interface Receipt {
  id: string;
  forecast: Forecast & { target_date: string; plan?: PlanSnapshot };
  actual: { within_band: boolean } | null;
  trades?: TradeRecord[];
  trade_summary?: TradeSummary;
  delivery?: Record<string, string>;
}

async function request(path: string, method = "GET", body?: unknown): Promise<Receipt> {
  const res = await fetch(path, {
    method, headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `요청 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

export function CollectionCard({ data, isSample }: { data: Forecast; isSample: boolean }) {
  const [amount, setAmount] = useState("300000");
  const [product, setProduct] = useState("금 현물");
  const [id, setId] = useState(() => localStorage.getItem("gold-receipt") ?? "");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [kind, setKind] = useState("boolean");
  const [value, setValue] = useState("true");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<Receipt>, saved: boolean) {
    setBusy(true); setMessage("");
    try {
      const result = await action();
      setReceipt(result); setId(result.id); localStorage.setItem("gold-receipt", result.id);
      setMessage(saved ? `DB 저장 성공. AWS: ${Object.entries(result.delivery ?? {}).map(([k, v]) => `${k}=${v}`).join(", ")}` : "접수 기록을 불러왔습니다.");
    } catch (err) { setMessage(String(err)); }
    finally { setBusy(false); }
  }

  function saveInput(event: FormEvent) {
    event.preventDefault();
    void run(() => request("/api/submissions", "POST", {
      forecast_date: data.as_of, weekly_amount: Number(amount), product,
    }), true);
  }

  function saveTrade(seq: number, tradeDate: string, price: number) {
    if (!receipt) return;
    void run(() => request(`/api/submissions/${receipt.id}/trades/${seq}`, "PUT", {
      trade_date: tradeDate, price,
    }), true);
  }

  function saveActual(event: FormEvent) {
    event.preventDefault();
    if (!receipt) return;
    void run(() => request(`/api/submissions/${receipt.id}/actual`, "PUT", {
      kind, value: kind === "boolean" ? value === "true" : Number(value),
      observed_on: receipt.forecast.target_date,
    }), true);
  }

  return <section className="card collection" aria-labelledby="collection-title">
    <h2 id="collection-title">입력값 · 매수 기록 · 실제 정답</h2>
    <p>주간 금액과 상품은 분할 계획용이며 AI 모델 입력값은 금 종가 수익률입니다.</p>
    <p>기준일 {data.as_of} · 실제 가격 단위: {data.currency}/{data.unit}. 예상 범위는 해당 금 기준가격에만 적용됩니다.</p>
    {isSample && <p role="alert">샘플 예측은 저장할 수 없습니다. API 연결 후 새로고침하세요.</p>}
    <form onSubmit={saveInput}>
      <label>저장할 주간 금액 (원) <input type="number" min="1" max="1000000000" step="1" required value={amount} onChange={e => setAmount(e.target.value)} /></label>
      <label>저장할 상품 <select value={product} onChange={e => setProduct(e.target.value)}>{["금 현물", "금 ETF", "기타"].map(p => <option key={p}>{p}</option>)}</select></label>
      <button disabled={busy || isSample}>입력값과 예측 저장</button>
    </form>
    <p>접수번호를 보관하세요. 번호를 아는 사람이 기록을 조회하고 정답을 수정할 수 있습니다.</p>
    <label>접수번호 <input value={id} onChange={e => { setId(e.target.value); setReceipt(null); }} /></label>
    <button disabled={busy || !id.trim()} onClick={() => void run(() => request(`/api/submissions/${encodeURIComponent(id.trim())}`), false)}>접수 기록 조회</button>
    {receipt && <TradeLog plan={receipt.forecast.plan} trades={receipt.trades ?? []} summary={receipt.trade_summary}
      unit={`${receipt.forecast.currency}/${receipt.forecast.unit}`} busy={busy} onSave={saveTrade} />}
    {receipt && <form onSubmit={saveActual}>
      <p>저장된 예측: {receipt.forecast.as_of} → 대상일 {receipt.forecast.target_date}, 범위 {receipt.forecast.band.low} ~ {receipt.forecast.band.high} {receipt.forecast.currency}/{receipt.forecast.unit}</p>
      <p>T/F는 대상일 종가가 위 범위 안이면 T, 밖이면 F입니다. 대상일 이후에 입력하세요. 휴장일 미설정 시 주말만 제외합니다.</p>
      <label>정답 입력 방식 <select value={kind} onChange={e => { setKind(e.target.value); setValue(e.target.value === "boolean" ? "true" : ""); }}><option value="boolean">T/F</option><option value="price">실제 종가</option></select></label>
      {kind === "boolean" ? <label>범위 포함 여부 <select value={value} onChange={e => setValue(e.target.value)}><option value="true">T (범위 안)</option><option value="false">F (범위 밖)</option></select></label> : <label>실제 금 종가 <input required type="number" min="0.000001" step="any" value={value} onChange={e => setValue(e.target.value)} /></label>}
      <button disabled={busy}>실제 정답 저장</button>
      {receipt.actual && <p>등록된 정답: {receipt.actual.within_band ? "T (범위 안)" : "F (범위 밖)"}</p>}
    </form>}
    <p role="status">{message}</p>
  </section>;
}
