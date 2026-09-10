import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// SMART AQI frontend. Dev server proxies /api to the Flask backend so the
// browser only ever talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
  // ensure the automatic JSX runtime is used in test transforms too
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
    pool: 'threads',
    testTimeout: 10000,
    hookTimeout: 15000,
  },
})
