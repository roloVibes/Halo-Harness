// Halo Studio's shell: React + Vite + TypeScript. `npm run build` writes the
// bundle to ../static/dist with stable names (studio.js, studio.css), which
// is committed so `uv tool install` needs no node, and (3.3.13.0 R2) each shipped pack's page module
// (vite.pack.config.ts). CI rebuilds and fails on drift. `npm run dev` proxies /api to a running
// `halo studio --no-open --port <p>` (HALO_STUDIO_PORT, default 8765).
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import { noRemoteUrls } from "./vite.shared";

declare const process: { env: Record<string, string | undefined> };
const studioPort = process.env.HALO_STUDIO_PORT || "8765";
const target = `http://127.0.0.1:${studioPort}`;

// Studio's guard answers a foreign Origin with 403, and the dev page is on Vite's port:
// the proxy drops the header (Host becomes Studio's own via changeOrigin).
function toStudio(): ProxyOptions {
  return {
    target,
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on("proxyReq", (proxyReq) => proxyReq.removeHeader("origin"));
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [react(), noRemoteUrls()],
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: false,
    modulePreload: { polyfill: false },
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        entryFileNames: "studio.js",
        chunkFileNames: "[name].js",
        assetFileNames: (info) => (info.names?.[0] ?? info.name ?? "").endsWith(".css") ? "studio.css" : "[name][extname]",
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": toStudio(),
    },
  },
});
