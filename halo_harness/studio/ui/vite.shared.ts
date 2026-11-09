// What both builds share (vite.config.ts: the shell; vite.pack.config.ts: a shipped pack's page module).
//
// noRemoteUrls: the output carries no remote URL -- Studio fetches nothing off the machine. Two string literals
// inside react-dom are not fetches but still spell a scheme: the XML/SVG namespace URIs and React's error-decoder
// link. They are written with an escaped slash (same string at runtime); any OTHER http(s) URL fails the build.
//
// shellLib (3.3.13.0 R2): a pack module takes React, ReactDOM and the shell's parts from the shell instead of bundling
// a copy: `react`, `react/jsx-runtime`, `react-dom`, `react-dom/client` and `@halo/<part>` become the matching key of
// `globalThis.__haloStudioLib` (packlib/index.ts LIB, the same object as the bundle api's `lib`), its named exports
// read from that object (Rollup's synthetic named exports).
import type { Plugin } from "vite";

const KNOWN_LITERALS = ["http://www.w3.org/", "https://react.dev/"];
const SLASH = "\\u002f";

export function noRemoteUrls(): Plugin {
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

const SHARED: Record<string, string> = {
  react: "React",
  "react/jsx-runtime": "jsxRuntime",
  "react/jsx-dev-runtime": "jsxRuntime",
  "react-dom": "ReactDOM",
  "react-dom/client": "ReactDOM",
};
const PREFIX = "\0halo-lib:";

export function shellLib(): Plugin {
  return {
    name: "halo-shell-lib",
    enforce: "pre",
    resolveId(id) {
      if (id in SHARED) return PREFIX + SHARED[id];
      const part = /^@halo\/([a-z]+)$/.exec(id)?.[1];
      return part ? PREFIX + part : null;
    },
    load(id) {
      if (!id.startsWith(PREFIX)) return null;
      const key = JSON.stringify(id.slice(PREFIX.length));
      const code = "const lib = globalThis.__haloStudioLib;\n" +
        `if (!lib || !lib[${key}]) throw new Error("this pack module runs inside Halo Studio: no shared " + ${key});\n` +
        `export default lib[${key}];\n`;
      return { code, syntheticNamedExports: true };
    },
  };
}
