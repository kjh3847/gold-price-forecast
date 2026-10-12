import { explainPercentile, formatDate, formatPct, halfWidth } from "./format";

describe("format", () => {
  it("날짜를 요일과 함께 표시한다", () => {
    expect(formatDate("2026-09-24")).toBe("2026년 9월 24일 (목)");
  });

  it("범위 반폭 비율", () => {
    expect(formatPct(halfWidth(4050.27, 4509.67, 4273.8))).toBe("5.4%");
  });

  it("백분위 해설: 상위·하위 표현, 방향 표현 없음", () => {
    expect(explainPercentile("높음", 0.82)).toBe("최근 1년 중 상위 18% 수준으로 출렁임이 큰 편이에요.");
    expect(explainPercentile("낮음", 0.1)).toContain("하위 10%");
    expect(explainPercentile("매우 높음", 1)).toContain("상위 1%");
    expect(explainPercentile("보통", null)).toContain("충분하지 않아요");
    for (const text of ["오를", "내릴", "사세요", "파세요"]) {
      expect(explainPercentile("높음", 0.95)).not.toContain(text);
    }
  });
});
