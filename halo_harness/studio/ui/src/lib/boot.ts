// What the served page says about this harness (studio/session_open.py boot_html, studio/setup_check_state.py
// boot_attrs) as data- attributes on <html>: read once on load. lib/store.ts re-exports these (3.3.2.0 R1: split
// out of it to keep it under the 250-line cap).
import type { PackSectionId } from "./store";

/** 3.1.4.0 R2: the served page names this harness's newest live session (studio/session_open.py boot_html). */
export function bootLiveSession(): string {
  try {
    return document.documentElement.dataset.liveSession || "";
  } catch {
    return "";
  }
}

/** A running pack's own section as the served page names it (`data-pack-sections`, 3.2.1.0 R1). */
export type BootPackSection = { id: PackSectionId; pack: string; title: string };

/** 3.2.1.0 R1: the running packs' sections the served page names (studio/session_open.py boot_html), so a saved
 *  pack section is the first paint; [] when the page names none (no pack runs, or an older server). */
export function bootPackSections(): BootPackSection[] {
  try {
    const raw = document.documentElement.dataset.packSections;
    const got: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(got)
      ? got.filter((s): s is BootPackSection => !!s && typeof s.id === "string" && s.id.includes("--") && typeof s.title === "string")
      : [];
  } catch {
    return [];
  }
}

/** 3.3.0.0 R3: the served page says no provider is set up yet (studio/setup_check_state.py boot_attrs). */
export function bootNoProvider(): boolean {
  try {
    return document.documentElement.dataset.noProvider === "1";
  } catch {
    return false;
  }
}
