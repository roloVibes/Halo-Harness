// Local's pages (3.3.5.0 R1, plans/ROADMAP.md "3.3.5.0 becomes Local"): seven,
// in this order -- Resources, Hosts, Models (built in R1), Library (R2: the
// library browser and the fit badge), Hugging Face (R4: HF local models),
// Benchmarks (R5: the speed card, tuning scans, revert) and Steward (R6: the
// steward's chat and the scheduling; R1 shows its status and last note). Which
// page is open is this store: the rail opens any, the door (`?page=`, door.ts)
// opens one, the palette's "Local: <page>" too, and the page last open is
// remembered for this browser under halo.studio.local.page.
import { createStore, useStore, writeLocal } from "../../lib/store";

export type PageId = "resources" | "hosts" | "models" | "library" | "huggingface" | "benchmarks" | "steward";
export type PageDef = { id: PageId; title: string; built: boolean; round?: string };

export const PAGES: PageDef[] = [
  { id: "resources", title: "Resources", built: true },
  { id: "hosts", title: "Hosts", built: true },
  { id: "models", title: "Models", built: true },
  { id: "library", title: "Library", built: false, round: "R2" },
  { id: "huggingface", title: "Hugging Face", built: false, round: "R4" },
  { id: "benchmarks", title: "Benchmarks", built: false, round: "R5" },
  { id: "steward", title: "Steward", built: false, round: "R6" },
];

export const PAGE_KEY = "halo.studio.local.page";
export const FIRST: PageId = "resources";

type Pages = { page: PageId; chosen: boolean; host: string };
export const pages = createStore<Pages>({ page: FIRST, chosen: false, host: "" });

export function usePage(): PageId {
  return useStore(pages, (s) => s.page);
}

/** A door's or the palette's word as a page ("hf" is Hugging Face); null for anything else. */
export function pageOf(word: string): PageId | null {
  const w = String(word || "").toLowerCase().replace(/\s+/g, "");
  if (w === "hf") return "huggingface";
  const hit = PAGES.find((p) => p.id === w || p.title.toLowerCase().replace(/\s+/g, "") === w);
  return hit ? hit.id : null;
}

export function titleOf(id: PageId): string {
  return PAGES.find((p) => p.id === id)?.title || id;
}

/** Open page `id` (the rail, the door, the palette, a link: `host` narrows Models to one host). */
export function goto(id: PageId, host?: string): void {
  pages.update(() => ({ page: id, chosen: true, ...(host !== undefined ? { host } : {}) }));
  writeLocal(PAGE_KEY, id);
}

/** The view drew: the page last open in this browser, unless one was chosen already. */
export function adoptRemembered(): void {
  if (pages.get().chosen) return;
  let saved = "";
  try {
    saved = localStorage.getItem(PAGE_KEY) || "";
  } catch {
    saved = "";
  }
  const p = pageOf(saved);
  if (p) pages.update(() => ({ page: p }));
}
