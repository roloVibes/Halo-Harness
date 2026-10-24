// What every harness can do (3.0.6.0 R6): the capability catalogs from
// `GET fleet/capabilities` (studio/fleet_capabilities_api.py) and the
// "Who can..." ranking from `GET fleet/who?q=`. Read when Fleet starts, again
// when a `fleet` frame says a catalog changed (action `capabilities`), and
// every few minutes while the tab shows. `focus` is the harness a Who result
// or a People "specs" link picked: its spec card opens and its map box lights.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { select } from "./actions";
import { showFleetPanel } from "./extras";
import { fleet, keyOf } from "./store";

export type Tool = { name: string; desc: string };
export type McpServer = { name: string; transport: string; tools: Tool[] | null; note?: string };
/** 3.2.0.0 R4: a pack's fleet capability on this harness (packs/fleet_registry.py), available here or not and why. */
export type PackCap = { name: string; description: string; available: boolean; why: string; checks: { key: string; ok: boolean; line: string }[]; capacity: { parallel?: number } };
/** 3.2.1.0 R3: an inspector line carries its file's text (the first 8 KB, `cut` when longer), so a member's shows here. */
export type InspectorEntry = { label: string; source: string; text?: string; cut?: boolean };
export type PackCaps = { id: string; name: string; version: string; capabilities: PackCap[]; inspector: InspectorEntry[]; metadata: Record<string, unknown> };
export type Catalog = {
  harness: { id: string; name: string; host?: string; os?: string; version?: string };
  at: number;
  hash: string;
  tags: string[];
  mcp: McpServer[];
  skills: string[];
  roles: { role: string; bio: string; lineup: string }[];
  providers: { name: string; id?: string; ok: boolean }[];
  models: { id: string; provider: string; best_for: string[]; local?: boolean }[];
  craft_apps: string[];
  media: { comfyui: boolean; models: { name: string; kind: string }[] };
  hardware: { os?: string; distro?: string; cpu?: string; cores?: number; ram_gb?: number; gpu?: { name: string; vram_gb: number | null }[]; disk_free_gb?: number };
  clis: Record<string, string | null>;
  projects: { name: string; repo: string; branch: string | null }[];
  integrations: Record<string, boolean>;
  packs?: PackCaps[];
};
export type CapsRow = { harness: string; name: string; local: boolean; online: boolean; hash: string | null; summary: string; chips: string[]; at: number | null; received: number | null; catalog: Catalog | null; note?: string };
export type WhoMatch = { kind: string; name: string; why: string; score: number };
export type WhoRow = { harness: string; name: string; local: boolean; score: number; matched: number; matches: WhoMatch[] };

type CapsState = {
  rows: CapsRow[] | null;
  error: string;
  busy: string;
  at: number;
  started: boolean;
  focus: string;
  open: Record<string, boolean>;
  q: string;
  who: WhoRow[] | null;
  whoError: string;
  whoBusy: boolean;
};

export const caps = createStore<CapsState>({ rows: null, error: "", busy: "", at: 0, started: false, focus: "", open: {}, q: "", who: null, whoError: "", whoBusy: false });

export function useCaps<S>(pick: (s: CapsState) => S): S {
  return useStore(caps, pick);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const POLL_MS = 180_000;

/** Every catalog; `harness` + refresh gathers that one afresh (this harness) or asks it now (a member). */
export async function loadCaps(refresh = false, harness = ""): Promise<void> {
  if (refresh) caps.update(() => ({ busy: harness || "local" }));
  try {
    const r = await api.get<{ harnesses: CapsRow[] }>("fleet/capabilities", refresh ? { refresh: 1, harness: harness || "local" } : undefined);
    if (refresh) {
      const fresh = r.harnesses || [];
      caps.update((s) => ({ rows: (s.rows || []).map((x) => fresh.find((f) => f.harness === x.harness) || x), error: "", at: Date.now() }));
      void loadCaps(false);
    } else caps.update(() => ({ rows: r.harnesses || [], error: "", at: Date.now() }));
    if (caps.get().q) void runWho(caps.get().q);
  } catch (e) {
    caps.update(() => ({ error: msg(e) }));
  } finally {
    if (refresh) caps.update(() => ({ busy: "" }));
  }
}

export async function runWho(q: string): Promise<void> {
  const text = q.trim();
  caps.update(() => ({ q, whoBusy: !!text, whoError: "", ...(text ? {} : { who: null }) }));
  if (!text) return;
  try {
    const r = await api.get<{ results: WhoRow[] }>("fleet/who", { q: text });
    if (caps.get().q === q) caps.update(() => ({ who: r.results || [], whoBusy: false }));
  } catch (e) {
    if (caps.get().q === q) caps.update(() => ({ who: [], whoError: msg(e), whoBusy: false }));
  }
}

/** Pick a harness: its spec card opens, its map box lights, its first live session's main agent is selected. */
export function focusHarness(hid: string, panel = ""): void {
  caps.update((s) => ({ focus: hid, open: { ...s.open, [hid]: true } }));
  const h = fleet.get().harnesses.find((x) => x.id === hid);
  const top = h?.sessions?.[0];
  if (h && top) select(keyOf(h.id, top.session_id, "main"));
  if (panel) showFleetPanel(panel);
  window.setTimeout(() => document.querySelector(`[data-testid="fleet-caps-card"][data-id="${CSS.escape(hid)}"]`)?.scrollIntoView({ block: "nearest" }), 120);
}

export function chipsFor(hid: string): string[] {
  return caps.get().rows?.find((r) => r.harness === hid)?.chips || [];
}

export function startCaps(): void {
  if (caps.get().started) return;
  caps.update(() => ({ started: true }));
  let pending = 0;
  onEvent("fleet", (f) => {
    const d = (f.data || {}) as { action?: string };
    if (d.action !== "capabilities") return;
    window.clearTimeout(pending);
    pending = window.setTimeout(() => void loadCaps(false), 200);
  });
  window.setInterval(() => !document.hidden && void loadCaps(false), POLL_MS);
  void loadCaps(false);
}
