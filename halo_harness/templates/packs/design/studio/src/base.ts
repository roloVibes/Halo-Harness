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

/** One of the pack's raw files (an artboard's, an asset): an iframe or a link sends no header, so `authUrl` (api.lib's
 *  client, scoped to this pack) adds the design pack's key in `?k=` (Halo 3.3.14.0): a GET-only key for this pack's own
 *  routes, never Studio's token, so a prototype that reads its own address finds nothing that opens Studio. */
export function rawUrl(rest: string, query = ""): string {
  return authUrl(`${BASE}/_files/${rest}${query ? "?" + query : ""}`);
}
