// Settings' pages (3.3.3.0 R2): one page per catalog group, in the catalog's
// order (General, Agents and roles, ... Local). Which page is open is this
// store: the rail opens any, the door (`?group=`, door.ts) opens one, a
// palette entry opens a row's group and lights the row for a moment, and the
// page last open is remembered for this browser under halo.studio.settings.page
// (Setup's key is per home; this one is not). The search box narrows the rows
// across every group; while it holds words the page shows the hits, a caption
// per group.
import { createStore, useStore, writeLocal } from "../../lib/store";
import { settings, type Row } from "./store";

export const PAGE_KEY = "halo.studio.settings.page";
export const FIRST = "general";

type Pages = { page: string; chosen: boolean; query: string; lit: string };
export const pages = createStore<Pages>({ page: FIRST, chosen: false, query: "", lit: "" });

export function usePages<S>(select: (s: Pages) => S): S {
  return useStore(pages, select);
}

export function isGroup(id: string): boolean {
  const groups = settings.get().groups;
  return groups.length ? groups.some((g) => g.id === id) : /^[a-z]+$/.test(id);
}

/** Open group `id`'s page (the rail, the door, a palette entry). */
export function goto(id: string): void {
  if (!isGroup(id)) return;
  pages.update(() => ({ page: id, chosen: true, query: "" }));
  writeLocal(PAGE_KEY, id);
}

/** The catalog arrived: the page last open in this browser, unless one was chosen already. */
export function adoptRemembered(): void {
  if (pages.get().chosen) return;
  let saved = "";
  try {
    saved = localStorage.getItem(PAGE_KEY) || "";
  } catch {
    saved = "";
  }
  if (saved && settings.get().groups.some((g) => g.id === saved)) pages.update(() => ({ page: saved }));
}

export function setQuery(query: string): void {
  pages.update(() => ({ query }));
}

/** Does `r` match every word of the search (its key, title, help or group title). */
export function hits(r: Row, query: string, groupTitle: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const text = `${r.key} ${r.title} ${r.help} ${groupTitle}`.toLowerCase();
  return words.every((w) => text.includes(w));
}

let litTimer = 0;

/** A palette entry: the row's page, the search cleared, the row lit for a moment (SettingsPage scrolls to it). */
export function openRow(key: string): void {
  const r = settings.get().rows.find((x) => x.key === key);
  if (!r) return;
  goto(r.group);
  pages.update(() => ({ lit: key }));
  window.clearTimeout(litTimer);
  litTimer = window.setTimeout(() => pages.update((s) => (s.lit === key ? { lit: "" } : {})), 1800);
}
