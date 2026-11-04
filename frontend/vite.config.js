import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Public origin used for canonical, og:url and og:image (crawlers need absolute
// URLs). Set VITE_SITE_URL at build time, e.g. VITE_SITE_URL=https://example.com.
// PLACEHOLDER: the production domain is not decided yet; replace this default
// (or always set VITE_SITE_URL) before sharing links.
const DEFAULT_SITE_URL = "https://reviewlens.example.com";

// Dev: serve the UI here and proxy /api to FastAPI (AGENTS.md, qa.md §8).
// Build: emit to dist/, which FastAPI serves in prod with an SPA fallback.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const fromEnv = env.VITE_SITE_URL || env.SITE_URL;
  if (!fromEnv && mode === "production") {
    console.warn(`[site-url] VITE_SITE_URL not set; using placeholder ${DEFAULT_SITE_URL}`);
  }
  const siteUrl = (fromEnv || DEFAULT_SITE_URL).replace(/\/+$/, "");

  return {
    plugins: [
      react(),
      {
        name: "site-url",
        // "pre" so the token is replaced before Vite parses the HTML's URLs.
        transformIndexHtml: {
          order: "pre",
          handler: (html) => html.replaceAll("%SITE_URL%", siteUrl),
        },
      },
    ],
    server: {
      proxy: {
        "/api": "http://localhost:8000",
      },
    },
    build: {
      outDir: "dist",
    },
  };
});
