import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import sample from "../../public/data/forecast.sample.json";
import { CollectionCard } from "./CollectionCard";
import { SimulationCard } from "./SimulationCard";
import type { Forecast, PolicyInfo } from "../types";

const data = sample as Forecast;
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

const plan = {
  policy_version: "policy-83df0498",
  n_splits: 2,
  items: [{ seq: 1, weekday: 0, amount: 150_000 }, { seq: 2, weekday: 3, amount: 150_000 }],
};

function receipt(trades: unknown[] = [], summary?: unknown) {
  return {
    id: "receipt-id",
    forecast: { ...data, target_date: "2026-10-01", plan },
    actual: null,
    trades,
    trade_summary: summary ?? { n_splits: 2, done: trades.length, total_amount: 0, avg_cost: null },
    delivery: { s3: "disabled", cloudwatch: "sent" },
  };
}

it("records a trade for each plan item and shows the average cost", async () => {
  const saved = receipt(
    [{ seq: 1, trade_date: "2026-09-28", price: 4000, amount: 150_000 }],
    { n_splits: 2, done: 1, total_amount: 150_000, avg_cost: 4000 },
  );
  const fetcher = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => receipt() })
    .mockResolvedValueOnce({ ok: true, json: async () => saved });
  vi.stubGlobal("fetch", fetcher);
  render(<CollectionCard data={data} isSample={false} />);

  fireEvent.click(screen.getByRole("button", { name: "입력값과 예측 저장" }));
  const log = await screen.findByLabelText("내 매수 기록");
  expect(within(log).getByText(/2회 분할 · policy-83df0498/)).toBeInTheDocument();
  expect(within(log).getAllByText("미기록")).toHaveLength(2);

  const first = within(log).getAllByRole("listitem")[0];
  fireEvent.change(within(first).getByLabelText("체결일"), { target: { value: "2026-09-28" } });
  fireEvent.change(within(first).getByLabelText(/체결 단가/), { target: { value: "4000" } });
  fireEvent.click(within(first).getByRole("button", { name: "기록" }));

  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(fetcher.mock.calls[1][0]).toBe("/api/submissions/receipt-id/trades/1");
  expect(fetcher.mock.calls[1][1].method).toBe("PUT");
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ trade_date: "2026-09-28", price: 4000 });
  expect(await screen.findByText(/1\/2회 기록/)).toBeInTheDocument();
  expect(screen.getByText(/4,000.00 USD\/oz/)).toBeInTheDocument();
  expect(screen.getByText(/cloudwatch=sent/)).toBeInTheDocument();
});

it("explains when an old receipt has no plan", async () => {
  const old = { ...receipt(), forecast: { ...data, target_date: "2026-10-01" } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => old }));
  render(<CollectionCard data={data} isSample={false} />);
  fireEvent.click(screen.getByRole("button", { name: "입력값과 예측 저장" }));
  expect(await screen.findByText(/분할 플랜이 없어요/)).toBeInTheDocument();
});

const policy: PolicyInfo = {
  version: "policy-83df0498",
  source: "trained",
  activated_at: "2026-11-09T08:10:00+00:00",
  cost_per_trade: 0.001,
  previous_version: "policy-896c2ac3",
  simulation: {
    weeks: 465, period_start: "2017-06-05", period_end: "2026-09-21", cost_per_trade: 0.001, avg_trades: 2.6,
    timing_error: 0.0018, timing_error_worst: 0.012, lump_timing_error: 0.0072, lump_timing_error_worst: 0.04,
    daily_timing_error: 0.0002, cheaper_than_lump_share: 0.5, reward: -0.0035,
    by_grade: { 낮음: { weeks: 150, n_splits: 2, timing_error: 0.0021, lump_timing_error: 0.0062 } },
  },
  training: {
    trained_at: "2026-11-09T08:10:00+00:00", holdout_weeks: 52, holdout_start: "2025-09-22",
    holdout_reward_current: -0.0047, holdout_reward_candidate: -0.0045, log_samples: 3,
    current_rule: { LOW: [0], NORMAL: [0, 3], HIGH: [0, 2, 4], VERY_HIGH: [0, 1, 2, 3, 4] },
    candidate_rule: { LOW: [0, 3], NORMAL: [0, 2, 4], HIGH: [0, 2, 4], VERY_HIGH: [0, 2, 4] },
    accepted: true, reason: "검증 기간 보상이 현재 규칙보다 높아 채택합니다",
  },
};

it("shows simulation results and the training history", () => {
  render(<SimulationCard policy={policy} />);
  expect(screen.getByText(/지난 465주/)).toBeInTheDocument();
  expect(screen.getByText(/평균 0.72% → 0.18%/)).toBeInTheDocument();
  expect(screen.getByText(/학습된 규칙 \(policy-83df0498\)/)).toBeInTheDocument();
  expect(screen.getByText(/이전: 낮음 1회 · 보통 2회 · 높음 3회 · 매우 높음 5회/)).toBeInTheDocument();
  expect(screen.getByText(/현재: 낮음 2회 · 보통 3회 · 높음 3회 · 매우 높음 3회/)).toBeInTheDocument();
  expect(screen.getByText(/사용자 매수 기록 3건/)).toBeInTheDocument();
});

it("handles a missing policy", () => {
  render(<SimulationCard policy={null} />);
  expect(screen.getByText(/시뮬레이션 결과가 아직 없어요/)).toBeInTheDocument();
});
