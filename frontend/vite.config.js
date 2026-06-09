import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: serve the UI here and proxy /api to FastAPI (AGENTS.md, qa.md §8).
// Build: emit to dist/, which FastAPI serves in prod with an SPA fallback.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
