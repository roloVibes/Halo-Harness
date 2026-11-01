// 3.3.7.0 R5: the Pack Manager's Bundles slice (Bundles.tsx; GET pack/bundles, studio/packs_bundles_api.py). A bundle
// is a pack with a resource claim; each row carries its honest verdict (ready / needs N downloads / won't work, with
// the ways out). The tick posts pack/bundle/<id>/on (only a ready bundle turns on; the claim is held by this Studio)
// and the untick pack/bundle/<id>/off. The verdict's one button starts the existing Download and verify job for each
// tag it names (POST local/library/verify). Nothing runs until a tick or a button is pressed.
import { api, ApiError } from "../../../lib/api";
import { onEvent } from "../../../lib/events";
import { createStore, useStore } from "../../../lib/store";

export type Need = { role: string; tag: string | null; gb: number | null; fits: boolean | null; minutes: number;
  download_gb: number | null; installed: boolean | null; runtime: string; placed: string; why: string };
export type Option = { says: string; frees_gb: number; kind: string };
export type Verdict = { bundle: string; host: string; state: "ready" | "downloads" | "wont" | "unknown"; says: string;
  needs: Need[]; downloads: Need[]; options: Option[]; button: { label: string; tags: string[]; host: string } | null;
  latency_ms: number | null; claims_line?: string };
export type BundleRow = { id: string; name: string; description: string; scope: string; installed: boolean; on: boolean;
  verdict: Verdict | null; cli: { verdict: string; on: string; off: string } };
type Said = { ok: boolean; lines: string[] };
type BState = { rows: BundleRow[] | null; error: string; busy: string; said: Record<string, Said> };

export const bstore = createStore<BState>({ rows: null, error: "", busy: "", said: {} });

export function useBundles<T>(pick: (s: BState) => T): T {
  return useStore(bstore, pick);
}

let started = false;

export async function loadBundles(): Promise<void> {
  try {
    const r = await api.get<{ bundles: BundleRow[] }>("pack/bundles");
    bstore.update(() => ({ rows: r.bundles, error: "" }));
  } catch (e) {
    bstore.update(() => ({ error: e instanceof ApiError ? e.message : String(e) }));
  }
}

export function startBundles(): void {
  if (started) return;
  started = true;
  onEvent("pack_changed", () => void loadBundles());
  void loadBundles();
}

function said(id: string, ok: boolean, lines: string[]): void {
  bstore.update((s) => ({ busy: "", said: { ...s.said, [id]: { ok, lines } } }));
}

/** The tick: on when it is off, off when it is on. */
export async function tick(row: BundleRow): Promise<void> {
  bstore.update(() => ({ busy: row.id }));
  try {
    const r = await api.post<{ lines?: string[] }>(`pack/bundle/${encodeURIComponent(row.id)}/${row.on ? "off" : "on"}`, {});
    said(row.id, true, r.lines || []);
  } catch (e) {
    const err = e instanceof ApiError ? e : null;
    said(row.id, false, err?.problems.length ? err.problems : [err ? err.message : String(e)]);
  }
  await loadBundles();
}

/** The verdict's one button: Download and verify, one job per tag it names. */
export async function download(row: BundleRow): Promise<void> {
  const b = row.verdict?.button;
  if (!b) return;
  bstore.update(() => ({ busy: row.id }));
  try {
    for (const name of b.tags) await api.post("local/library/verify", { host: b.host, name });
    said(row.id, true, [`downloading ${b.tags.join(", ")} onto ${b.host}, then the battery on each (the Jobs list on Local shows them)`]);
  } catch (e) {
    said(row.id, false, [e instanceof ApiError ? e.message : String(e)]);
  }
}
