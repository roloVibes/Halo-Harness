// Where the design pack lives in Studio: its section (`design--design`), its routes under /api/ (server/routes.py,
// `packs/design/design/...`) and the bundle api Studio handed `mount` (main.tsx keeps it here for the modules that
// need it after: the palette lines, the live frames).
import { authUrl } from "@halo/api";
import type { BundleApi } from "@halo/bundle";

export const PACK = "design";
export const SECTION = "design--design";
export const BASE = "packs/design/design";

let current: BundleApi | null = null;

export function setApi(api: BundleApi | null): void {
  current = api;
}

export function packApi(): BundleApi | null {
  return current;
}

/** One of the pack's raw files (an artboard's, an asset) with the token in `?t=`: an iframe or a link sends no header. */
export function rawUrl(rest: string, query = ""): string {
  return authUrl(`${BASE}/_files/${rest}${query ? "?" + query : ""}`);
}
