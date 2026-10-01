import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
  proxy: {
    "/vendors": {
      target: "http://127.0.0.1:8001",
      changeOrigin: true,
    },
    "/invoices": {
      target: "http://127.0.0.1:8001",
      changeOrigin: true,
    },
    "/payment-runs": {
      target: "http://127.0.0.1:8002",
      changeOrigin: true,
    },
    "/reports": {
      target: "http://127.0.0.1:8002",
      changeOrigin: true,
    },
  },
},
})
