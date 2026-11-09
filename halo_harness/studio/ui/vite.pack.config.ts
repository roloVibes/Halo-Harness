// A shipped pack's page module (3.3.13.0 R2, extension API 1.2): the design pack's Studio section, built from its
// sources (halo_harness/templates/packs/design/studio/src) into ONE ES module, studio/design.js beside them, which
// the pack's pack.yaml names as its section's view. `npm run build` builds it after the shell; it is committed like
// the dist, and the dist drift gate covers it (built twice, identical). React, ReactDOM and the shell's parts are not
// in it: shellLib maps them to the shell's own (vite.shared.ts), its CSS rides in as text (`?inline`) and goes on
// the page as a constructed stylesheet.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { noRemoteUrls, shellLib } from "./vite.shared";

const PACK = "../../templates/packs/design/studio";

export default defineConfig({
  base: "./",
  publicDir: false,
  plugins: [shellLib(), react(), noRemoteUrls()],
  build: {
    outDir: PACK,
    emptyOutDir: false, // the sources live there too
    sourcemap: false,
    minify: true,
    reportCompressedSize: false,
    lib: { entry: `${PACK}/src/main.tsx`, formats: ["es"], fileName: () => "design.js" },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
