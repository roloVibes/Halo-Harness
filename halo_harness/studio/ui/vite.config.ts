// Halo Studio's shell: React + Vite + TypeScript. `npm run build` writes the
// bundle to ../static/dist with stable names (studio.js, studio.css), which
// is committed so `uv tool install` needs no node. CI rebuilds and fails on
// drift. `npm run dev` proxies /api and /design-files to a running
// `halo studio --no-open --port <p>` (HALO_STUDIO_PORT, default 8765).
import { defineConfig, type Plugin, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

declare const process: { env: Record<string, string | undefined> };
const studioPort = process.env.HALO_STUDIO_PORT || "8765";
const target = `http://127.0.0.1:${studioPort}`;

// The dist carries no remote URL: Studio fetches nothing off the machine.
// Two string literals inside react-dom are not fetches but still spell a
// scheme: the XML/SVG namespace URIs and React's error-decoder link. They
// are written with an escaped slash (same string at runtime); any OTHER
// http(s) URL in the output fails the build.
const KNOWN_LITERALS = ["http://www.w3.org/", "https://react.dev/"];
const SLASH = "\\u002f";

function noRemoteUrls(): Plugin {
  return {
    name: "halo-no-remote-urls",
    enforce: "post",
    generateBundle(_opts, bundle) {
      for (const item of Object.values(bundle)) {
        if (item.type === "chunk") {
          for (const lit of KNOWN_LITERALS) {
            item.code = item.code.split(lit).join(lit.replace("//", SLASH + SLASH));
          }
          if (/https?:\/\//.test(item.code)) {
            const at = item.code.search(/https?:\/\//);
            this.error(`remote URL in ${item.fileName}: ${item.code.slice(at, at + 80)}`);
          }
        } else if (typeof item.source === "string" && /https?:\/\//.test(item.source)) {
          this.error(`remote URL in ${item.fileName}`);
        }
      }
    },
  };
}

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
      "/design-files": toStudio(),
      "/legacy": toStudio(),
    },
  },
});
