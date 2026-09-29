// Purpose: same-origin browser sessions and authenticated WebSocket proxying during local development.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1", port: 5173,
    proxy: { "/api": { target: process.env.BACKEND_URL || "http://127.0.0.1:8000", ws: true, changeOrigin: false } },
  },
  build: { sourcemap: false },
});
