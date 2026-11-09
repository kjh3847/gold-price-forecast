import "@testing-library/jest-dom/vitest";

// Recharts ResponsiveContainer가 jsdom에서 쓰는 API
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// Node 25+ 는 --localstorage-file 없이 빈 localStorage 전역을 노출해 jsdom 것을 가린다 → 메모리 구현으로 대체
if (typeof globalThis.localStorage?.getItem !== "function") {
  const store = new Map<string, string>();
  const memoryStorage: Storage = {
    get length() { return store.size; },
    clear: () => store.clear(),
    getItem: (key) => store.get(key) ?? null,
    key: (index) => [...store.keys()][index] ?? null,
    removeItem: (key) => { store.delete(key); },
    setItem: (key, value) => { store.set(key, String(value)); },
  };
  Object.defineProperty(globalThis, "localStorage", { value: memoryStorage, configurable: true });
}
