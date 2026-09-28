import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (/node_modules[/\\](recharts|d3-|victory-vendor)/.test(id)) return 'charts';
        },
      },
    },
  },
});
