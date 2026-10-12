import "@testing-library/jest-dom/vitest";

// Recharts ResponsiveContainer가 jsdom에서 쓰는 API
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
