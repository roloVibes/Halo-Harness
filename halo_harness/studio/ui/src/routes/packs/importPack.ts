// A pack's own module, imported (3.3.14.0 R1, the review's #4 and #5): PackView (a section's view) and PackBundle (a
// bundle panel) load it through here. Its URL carries the pack's key in `?k=` (the registry's, `GET pack/registry`),
// never the launch token. Imports run one at a time, and while one runs the global `__haloStudioLib` is that pack's
// lib (packlib/index.ts libFor): the module's `@halo/<part>` reads, made as it is evaluated, take its own scoped
// client. The global goes back to LIB (a client scoped to no pack) once the import settles. 3.4.1.2 (PACKS-2): the
// first import waits until lib/owner.ts has made the owner proof, so no pack script runs while it is being made.
import { ownerReady } from "../../lib/owner";
import { installLib, LIB, libFor } from "../../packlib";
import { packs } from "./store";

let queue: Promise<unknown> | null = null;

/** The pack's key from the registry ("" before the registry has answered). */
export function packKey(pack: string): string {
  return packs.get().reg.packs.find((x) => x.id === pack)?.key || "";
}

/** `import()` of the pack's file (`api/pack/<id>/file/<path>`, the registry's), with its own lib in place. */
export function importPack<T>(pack: string, file: string): Promise<T> {
  const key = packKey(pack);
  const url = new URL(`${file}?k=${encodeURIComponent(key)}`, location.origin + "/").href;
  const run = async (): Promise<T> => {
    installLib(libFor(pack, key));
    try {
      return (await import(/* @vite-ignore */ url)) as T;
    } finally {
      installLib(LIB);
    }
  };
  const next = (queue || ownerReady()).then(run, run);
  queue = next.catch(() => undefined);
  return next;
}
