import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Forecast } from "../types";
import { isForecast } from "../data";

interface PriceStatus {
  last_price_date: string | null;
  expected_through: string;
  missing_count: number;
  required_from: string | null;
  required_to: string | null;
  needs_upload: boolean;
  source_url: string;
  download_url: string;
  calendar_note: string;
  cutoff_note: string;
}

export function DataUpdate({ onUpdated }: { onUpdated: (forecast: Forecast) => void }) {
  const [status, setStatus] = useState<PriceStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/prices/status", { cache: "no-store" }).then(async response => {
      if (!response.ok) throw new Error("데이터 상태 확인에 실패했습니다.");
      const result = await response.json() as PriceStatus;
      if (!cancelled) { setStatus(result); setOpen(result.needs_upload); }
    }).catch(() => !cancelled && setMessage("최신성 확인 불가: API 연결을 확인하세요."));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    if (!open && dialog.current?.open) dialog.current?.close();
  }, [open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    if (file.size > 2_000_000) { setMessage("CSV는 2MB 이하로 올려주세요."); return; }
    setBusy(true); setMessage("");
    try {
      const response = await fetch("/api/prices/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ csv_text: await file.text() }) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "CSV 형식 또는 파일 크기를 확인하세요.");
      if (!isForecast(result.forecast)) throw new Error("예측 응답 형식이 올바르지 않습니다.");
      setStatus(result.data_status); onUpdated(result.forecast);
      setMessage(`${result.added_count}일 가격 저장 · 예측 갱신 완료. 재학습 ${result.retrained_dates.length}회 (기존 주기 유지).`);
      setOpen(false); setFile(null);
    } catch (err) { setMessage(String(err)); }
    finally { setBusy(false); }
  }

  return <section className="card data-update" aria-label="가격 데이터 업데이트">
    <h2>가격 데이터 업데이트</h2>
    {status ? <>
      <p>마지막 가격: {status.last_price_date ?? "없음"} · 확인 대상: {status.expected_through}까지 · 누락 {status.missing_count}거래일</p>
      {status.needs_upload && <p role="alert">가격 데이터가 부족합니다. 현재 표시된 예측은 과거 기준입니다.</p>}
      {status.missing_count > 0 && !status.needs_upload && <p>최신 종가가 일부 누락됐습니다. 5거래일 이상 누락되면 자동 안내합니다.</p>}
    </> : <p>가격 데이터 상태를 확인하는 중입니다.</p>}
    <button onClick={() => setOpen(true)} disabled={!status || busy}>CSV로 가격 업데이트</button>
    <p role="status">{!open && message}</p>
    <dialog ref={dialog} aria-labelledby="update-title" onCancel={event => { if (busy) event.preventDefault(); else setOpen(false); }}>
      <h2 id="update-title">금 가격 데이터가 필요합니다</h2>
      {status?.required_from ? <p><strong>{status.required_from}부터 {status.required_to}까지</strong> {status.missing_count}거래일의 데이터가 필요합니다.</p> : <p>최신 금 가격 CSV를 올려주세요.</p>}
      <p>GoldPrice.com에서 받은 날짜별 금 가격(USD/oz)을 사용하세요. 주간 금액이나 실제 정답 입력과는 별개입니다.</p>
      {status && <p><a href={status.source_url} target="_blank" rel="noreferrer">원본 사이트 열기</a> · <a href={status.download_url} target="_blank" rel="noreferrer">최신 CSV 다운로드</a></p>}
      <p>전체 원본 CSV를 올려도 됩니다. 기존 값은 비교 후 보존하고 새 날짜만 추가합니다. 다른 사이트의 현물·선물 가격을 섞지 마세요.</p>
      <p>{status?.cutoff_note} · 달력: {status?.calendar_note}. 휴장일은 서버 설정으로 관리합니다.</p>
      <form onSubmit={submit}>
        <label>금 가격 CSV 파일 <input type="file" accept=".csv,text/csv" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
        <p>허용 열: date + close_usd_per_troy_oz (또는 gold, close). 최대 2MB.</p>
        <button disabled={busy || !file}>{busy ? "가격 검증·예측 계산 중…" : "CSV 업로드하고 예측 갱신"}</button>
        <button type="button" disabled={busy} onClick={() => setOpen(false)}>나중에 입력</button>
      </form>
      <p role="status">{open && message}</p>
      <p>기존 모델은 63거래일 주기로 재학습합니다. 업로드 때마다 무조건 새로 학습하지 않습니다.</p>
    </dialog>
  </section>;
}
