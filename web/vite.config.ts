/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // Recharts 포함 단일 번들 (~560kB, gzip ~160kB) — 정적 시연용으로 충분
  build: { chunkSizeWarningLimit: 700 },
  server: {
    proxy: {
      "/api" : "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});