// The packs' Studio store (3.2.0.0 R3): the registry the server builds from
// the packs that run here (`GET pack/registry`), loaded once and again on
// every `pack_changed` frame (enable, disable, install, update, remove --
// in this process or from another terminal), and the pack's own
// `pack_event` frames (the events panels, Session's Live column and Fleet's
// Activity read them). A section of a pack that is gone takes you back to
// the first tab; a pack section you were on comes back on a reload.
import { useEffect } from "react";
import { api } from "../../lib/api";
import { onEvent, type FeedFrame } from "../../lib/events";
import { createStore, goSection, SECTION_IDS, studio, useStore, type SectionId } from "../../lib/store";
import type { PackFrame, PackPanel, Registry } from "./types";

export type PacksState = { reg: Registry; loaded: boolean; error: string; frames: PackFrame[] };

const EMPTY: Registry = { version: 1, core: [], packs: [] };
const MAX_FRAMES = 300;
export const packs = createStore<PacksState>({ reg: EMPTY, loaded: false, error: "", frames: [] });

export function usePacks<S>(select: (s: PacksState) => S): S {
  return useStore(packs, select);
}

let started = false;
let loading: Promise<void> | null = null;
let again = false;
let restored = false;
let seq = 0;

/** Every pack section id the registry holds. */
export function packSectionIds(reg: Registry = packs.get().reg): string[] {
  return reg.packs.flatMap((p) => p.sections.map((s) => s.id));
}

/** One panel of the registry by its qualified id (in a pack's section or a core one). */
export function findPanel(id: string, reg: Registry = packs.get().reg): PackPanel | undefined {
  for (const p of reg.packs) {
    for (const s of p.sections) for (const x of s.panels) if (x.id === id) return x;
    for (const x of p.panels) if (x.id === id) return x;
  }
  return undefined;
}

function afterLoad(reg: Registry): void {
  const ids = packSectionIds(reg);
  const cur = studio.get().section;
  if (cur.includes("--") && !ids.includes(cur)) goSection(SECTION_IDS[0]); // its pack is off now: nothing of it shows
  if (restored) return;
  restored = true;
  let saved = "";
  try {
    saved = localStorage.getItem("halo.studio.section") || "";
  } catch {
    saved = "";
  }
  if (saved.includes("--") && ids.includes(saved) && !/[?&]mode=/.test(location.search)) goSection(saved as SectionId);
}

export async function loadRegistry(): Promise<void> {
  if (loading) {
    again = true;
    return loading;
  }
  loading = (async () => {
    try {
      const got = await api.get<Registry>("pack/registry");
      const reg: Registry = { ...EMPTY, ...got, packs: Array.isArray(got.packs) ? got.packs : [] };
      packs.update(() => ({ reg, loaded: true, error: "" }));
      afterLoad(reg);
    } catch (e) {
      packs.update(() => ({ loaded: true, error: e instanceof Error ? e.message : String(e) })); // an older Studio: no packs
    } finally {
      loading = null;
    }
    if (again) {
      again = false;
      await loadRegistry();
    }
  })();
  return loading;
}

function onPackEvent(f: FeedFrame): void {
  const d = (f.data || {}) as { pack?: unknown; kind?: unknown; data?: unknown; problems?: unknown };
  if (typeof d.pack !== "string" || typeof d.kind !== "string") return;
  const frame: PackFrame = { pack: d.pack, kind: d.kind, data: d.data ?? null, ts: Number(f.ts) || Date.now() / 1000, n: ++seq };
  if (Array.isArray(d.problems) && d.problems.length) frame.problems = d.problems.map(String); // 3.2.0.0 R5: shown, never dropped
  packs.update((s) => ({ frames: [...s.frames, frame].slice(-MAX_FRAMES) }));
}

/** Start once (App): the first read and the two feed handlers. */
export function startPacks(): void {
  if (started) return;
  started = true;
  onEvent("pack_changed", () => void loadRegistry());
  onEvent("pack_event", onPackEvent);
  void loadRegistry();
}

/** The registry, started on first use. */
export function usePackRegistry(): Registry {
  useEffect(() => startPacks(), []);
  return usePacks((s) => s.reg);
}
