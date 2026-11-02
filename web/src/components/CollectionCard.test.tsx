import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import sample from "../../public/data/forecast.sample.json";
import { CollectionCard } from "./CollectionCard";
import type { Forecast } from "../types";

const data = sample as Forecast;
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

it("disables saving sample predictions", () => {
  render(<CollectionCard data={data} isSample />);
  expect(screen.getByRole("button", { name: "입력값과 예측 저장" })).toBeDisabled();
});

it("saves inputs, retrieves a receipt, and submits both truth formats", async () => {
  const receipt = { id: "receipt-id", forecast: { ...data, target_date: "2026-10-01" }, actual: null, delivery: { s3: "disabled", cloudwatch: "disabled" } };
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => receipt });
  vi.stubGlobal("fetch", fetcher);
  render(<CollectionCard data={data} isSample={false} />);
  fireEvent.click(screen.getByRole("button", { name: "입력값과 예측 저장" }));
  await screen.findByText(/DB 저장 성공/);
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ forecast_date: data.as_of, weekly_amount: 300000, product: "금 현물" });
  expect(localStorage.getItem("gold-receipt")).toBe("receipt-id");
  fireEvent.click(screen.getByRole("button", { name: "실제 정답 저장" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ kind: "boolean", value: true, observed_on: "2026-10-01" });
  await screen.findByText(/DB 저장 성공/);
  fireEvent.change(screen.getByLabelText("정답 입력 방식"), { target: { value: "price" } });
  fireEvent.change(screen.getByLabelText("실제 금 종가"), { target: { value: "4100" } });
  fireEvent.click(screen.getByRole("button", { name: "실제 정답 저장" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
  expect(JSON.parse(fetcher.mock.calls[2][1].body).value).toBe(4100);
  await screen.findByText(/DB 저장 성공/);
  fireEvent.click(screen.getByRole("button", { name: "접수 기록 조회" }));
  await screen.findByText("접수 기록을 불러왔습니다.");
  expect(fetcher.mock.calls[3][0]).toBe("/api/submissions/receipt-id");
});

it("shows server errors without claiming success", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "기준일 변경" }) }));
  render(<CollectionCard data={data} isSample={false} />);
  fireEvent.click(screen.getByRole("button", { name: "입력값과 예측 저장" }));
  expect(await screen.findByText(/기준일 변경/)).toBeInTheDocument();
  expect(screen.queryByText(/DB 저장 성공/)).not.toBeInTheDocument();
});
