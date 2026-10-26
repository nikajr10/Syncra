import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// The API runs on :8000 (`make run`); /api/* is passed to it, so the browser never crosses origins.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // React, Motion and React Query in their own file: it stays cached in the browser when only the app changes.
  build: {
    rolldownOptions: {
      output: { codeSplitting: { groups: [{ name: 'vendor', test: /node_modules\/(react|react-dom|scheduler|motion|motion-dom|motion-utils|framer-motion|@tanstack)\// }] } },
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
})
