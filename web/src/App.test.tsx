import { fireEvent, render, screen } from "@testing-library/react";
import sample from "../public/data/forecast.sample.json";
import App from "./App";
import { FORECAST_URL, SAMPLE_URL, loadForecast } from "./data";

function mockFetch(routes: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    if (!(url in routes)) return new Response("not found", { status: 404 });
    return new Response(JSON.stringify(routes[url]), { status: 200 });
  }) as unknown as typeof fetch;
}

afterEach(() => vi.unstubAllGlobals());

describe("loadForecast", () => {
  it("forecast.json이 있으면 그것을 쓴다", async () => {
    const result = await loadForecast(mockFetch({ [FORECAST_URL]: sample, [SAMPLE_URL]: sample }));
    expect(result.isSample).toBe(false);
  });

  it("없거나 형식이 틀리면 샘플로 대체한다", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect((await loadForecast(mockFetch({ [SAMPLE_URL]: sample }))).isSample).toBe(true);
    expect((await loadForecast(mockFetch({ [FORECAST_URL]: { foo: 1 }, [SAMPLE_URL]: sample }))).isSample).toBe(true);
  });
});

describe("App", () => {
  it("샘플 데이터로 모든 섹션을 그리고 '샘플 데이터'를 표시한다", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", mockFetch({ [SAMPLE_URL]: sample }));
    render(<App />);

    expect(await screen.findByText(/샘플 데이터/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "금 분할매수 도우미" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "이번 주 변동성 날씨" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /다음 5거래일 90% 가격 범위/ })).toBeInTheDocument();
    expect(screen.getByText("4,050 ~ 4,510 달러")).toBeInTheDocument();
    expect(screen.getByText("(±5.4%)")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "모델 성적표" })).toBeInTheDocument();
    expect(screen.getByText(/수익을 보장하지 않습니다/)).toBeInTheDocument();
  });

  it("실데이터면 샘플 표시가 없고, 계산기가 금액을 나눈다", async () => {
    const data = { ...sample, grade: "높음" };
    vi.stubGlobal("fetch", mockFetch({ [FORECAST_URL]: data }));
    render(<App />);

    const input = await screen.findByLabelText("주간 매수 금액(원)");
    expect(screen.queryByText(/샘플 데이터/)).not.toBeInTheDocument();
    fireEvent.change(input, { target: { value: "100,000" } });
    const items = screen.getAllByRole("listitem").filter((li) => li.textContent?.includes("회차"));
    expect(items.map((li) => li.textContent)).toEqual([
      "1회차월요일33,333원",
      "2회차수요일33,333원",
      "3회차금요일33,334원",
    ]);
    fireEvent.change(input, { target: { value: "abc" } });
    expect(screen.getByText(/숫자로 입력해 주세요/)).toBeInTheDocument();
  });

  it("방향·매매 권유 표현이 없다", async () => {
    vi.stubGlobal("fetch", mockFetch({ [FORECAST_URL]: sample }));
    const { container } = render(<App />);
    await screen.findByText("모델 성적표");
    const text = container.textContent ?? "";
    for (const phrase of ["사세요", "파세요", "오를 것", "내릴 것", "상승할", "하락할"]) {
      expect(text).not.toContain(phrase);
    }
  });
});
