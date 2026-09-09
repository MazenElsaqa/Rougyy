import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// The FastAPI service (backend/main.py) is reachable at /api in every
// environment (Vercel strips the routePrefix before forwarding), so the
// dev server proxies /api the same way production routing does — no
// separate localhost URL needs to be hardcoded anywhere in the app.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
})
