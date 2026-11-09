import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import sample from "../../public/data/forecast.sample.json";
import { DataUpdate } from "./DataUpdate";

const stale = { last_price_date: "2026-09-24", expected_through: "2026-10-01", missing_count: 5, required_from: "2026-09-25", required_to: "2026-10-01", needs_upload: true, source_url: "https://goldprice.com/gold-price-history", download_url: "https://goldprice.com/gold-price-history.csv", calendar_note: "주말만 제외", cutoff_note: "뉴욕 기준 전일까지" };
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});
afterEach(() => vi.unstubAllGlobals());

it("automatically requests the exact range and refreshes the forecast after upload", async () => {
  const updated = vi.fn();
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => stale }).mockResolvedValueOnce({ ok: true, json: async () => ({ added_count: 5, retrained_dates: [], forecast: sample, data_status: { ...stale, needs_upload: false, missing_count: 0 } }) });
  vi.stubGlobal("fetch", fetcher);
  render(<DataUpdate onUpdated={updated} />);
  expect(await screen.findByText("2026-09-25부터 2026-10-01까지")).toBeInTheDocument();
  expect(screen.getByRole("dialog")).toHaveAttribute("open");
  const file = new File(["date,close\n2026-09-25,4284.97"], "prices.csv", { type: "text/csv" });
  Object.defineProperty(file, "text", { value: async () => "date,close\n2026-09-25,4284.97" });
  fireEvent.change(screen.getByLabelText("금 가격 CSV 파일"), { target: { files: [file] } });
  fireEvent.submit(screen.getByRole("button", { name: "CSV 업로드하고 예측 갱신" }).closest("form")!);
  await waitFor(() => expect(updated).toHaveBeenCalledWith(sample));
  expect(JSON.parse(fetcher.mock.calls[1][1].body).csv_text).toContain("4284.97");
  expect(await screen.findByText(/5일 가격 저장/)).toBeInTheDocument();
});

it("does not open automatically for fewer than 5 missing trading days", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...stale, needs_upload: false, missing_count: 4 }) }));
  render(<DataUpdate onUpdated={vi.fn()} />);
  await screen.findByText(/누락 4거래일/);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "CSV로 가격 업데이트" }));
  expect(screen.getByRole("dialog")).toHaveAttribute("open");
});

it("keeps the old forecast and dialog on rejected CSV", async () => {
  const updated = vi.fn();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({ ok: true, json: async () => stale }).mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "거래일이 아직 부족합니다" }) }));
  render(<DataUpdate onUpdated={updated} />);
  await screen.findByText("2026-09-25부터 2026-10-01까지");
  const file = new File(["bad"], "bad.csv");
  Object.defineProperty(file, "text", { value: async () => "bad" });
  fireEvent.change(screen.getByLabelText("금 가격 CSV 파일"), { target: { files: [file] } });
  fireEvent.submit(screen.getByRole("button", { name: "CSV 업로드하고 예측 갱신" }).closest("form")!);
  await screen.findByText(/거래일이 아직 부족합니다/);
  expect(updated).not.toHaveBeenCalled();
  expect(screen.getByRole("dialog")).toHaveAttribute("open");
});
