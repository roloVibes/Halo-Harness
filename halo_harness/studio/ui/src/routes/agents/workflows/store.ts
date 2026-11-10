// The Workflows board's store (3.3.16.0 R3, docs/STUDIO-agents.md "Workflows"): what GET workflows answers (every square
// with its contract, the active lineup's enabled refs), the library's open state and search, the selected / hovered /
// focused square, the inspector's page, the confirm card a drop raises, and the one line the last change said. Nothing
// here opens on load: the library, the inspector and the confirm card start closed.
import { api } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import { allAgents, isLive, type FleetState } from "../../fleet/store";

export type Square = {
  ref: string; group: "yours" | "packs" | "shipped"; origin: string; enabled: boolean; writable?: boolean; square: boolean;
  line: string; path: string; does: string; takes: string[]; gives: string[]; covers: string[];
  lead: { bio: string; model: string } | null; lineup: unknown; engine: string; band: string; cap_usd: number | null;
  depth: number; turns: number | null; wall_s: number | null; costs: string; limits: string;
};
export type Board = { lineup: string | null; where: string; enabled: string[]; squares: Square[] };
export type Page = "summary" | "purpose" | "agents" | "enable" | "budget" | "limits" | "yaml" | "remove"; // 3.3.16.3: purpose, agents

export type WfState = {
  board: Board | null; error: string; loading: boolean;
  library: boolean; query: string;
  selected: string; hover: string; focus: string; page: Page;
  confirm: string; note: string; busy: boolean;
};

export const wf = createStore<WfState>({
  board: null, error: "", loading: false, library: false, query: "", selected: "", hover: "", focus: "", page: "summary",
  confirm: "", note: "", busy: false,
});

export const useWf = <S,>(pick: (s: WfState) => S): S => useStore(wf, pick);

export async function loadBoard(): Promise<void> {
  wf.update(() => ({ loading: true }));
  try {
    const board = await api.get<Board>("workflows");
    wf.update(() => ({ board, error: "", loading: false }));
  } catch (e) {
    wf.update(() => ({ error: (e as Error).message || "could not read the squares", loading: false }));
  }
}

export const squareOf = (s: WfState, ref: string): Square | undefined => s.board?.squares.find((q) => q.ref === ref);
export const onBoard = (s: WfState): Square[] =>
  (s.board?.enabled || []).map((ref) => squareOf(s, ref)).filter((q): q is Square => !!q && q.square);

/** The library's rows by group, filtered by the search box (ref, DOES, covers). */
export function libraryRows(s: WfState): Record<"yours" | "packs" | "shipped", Square[]> {
  const q = s.query.trim().toLowerCase();
  const out = { yours: [] as Square[], packs: [] as Square[], shipped: [] as Square[] };
  for (const sq of s.board?.squares || []) {
    const hay = `${sq.ref} ${sq.does} ${sq.covers.join(" ")}`.toLowerCase();
    if (!q || hay.includes(q)) out[sq.group].push(sq);
  }
  return out;
}

export function openLibrary(focusSearch = false): void {
  wf.update(() => ({ library: true }));
  if (focusSearch) window.setTimeout(() => document.querySelector<HTMLInputElement>("[data-testid=wf-search]")?.focus(), 0);
}
export const closeLibrary = (): void => wf.update(() => ({ library: false }));
export const toggleLibrary = (): void => wf.update((s) => ({ library: !s.library }));

export const select = (ref: string, page: Page = "summary"): void => wf.update(() => ({ selected: ref, focus: ref || "", page }));
export const setPage = (page: Page): void => wf.update(() => ({ page }));
export const setHover = (ref: string): void => wf.update((s) => (s.hover === ref ? {} : { hover: ref }));

/** A row dropped on the board: the confirm card for it (an enabled one only says so). */
export function dropped(ref: string): void {
  const s = wf.get();
  const sq = squareOf(s, ref);
  if (!sq) return;
  if (s.board?.enabled.includes(ref)) wf.update(() => ({ note: `${ref} is on the board already` }));
  else wf.update(() => ({ confirm: ref }));
}
export const cancelConfirm = (): void => wf.update(() => ({ confirm: "" }));

async function flip(ref: string, on: boolean): Promise<void> {
  wf.update(() => ({ busy: true }));
  try {
    const got = await api.post<{ ok: boolean; line: string }>(on ? "workflows/enable" : "workflows/disable", { ref });
    wf.update((s) => ({ note: got.line, confirm: "", busy: false, ...(on ? {} : s.selected === ref ? { selected: "", page: "summary" as Page } : {}) }));
  } catch (e) {
    wf.update(() => ({ note: (e as Error).message || "the change did not save", busy: false }));
  }
  await loadBoard();
}
export const enableSquare = (ref: string): Promise<void> => flip(ref, true);
export const disableSquare = (ref: string): Promise<void> => flip(ref, false);

export async function saveContract(ref: string, body: { budget?: object; limits?: object; does?: string }): Promise<string> {
  try {
    const got = await api.put<{ ok: boolean; line: string }>("workflows/contract", { ref, ...body });
    wf.update(() => ({ note: got.line }));
    await loadBoard();
    return "";
  } catch (e) {
    return (e as Error).message || "not saved";
  }
}

/** The square at work now: a live agent row of this halo's sessions that carries `square` (workflows/receipts.py), as
 *  "<name>|<cost>" (a string, so a store selector stays stable); "" when none works. */
export function workingSquare(s: FleetState): string {
  const hit = allAgents(s).find((r) => r.h.local && r.a.square && isLive(r.a));
  return hit?.a.square ? `${hit.a.square.name}|${Number(hit.a.cost_usd) || 0}` : "";
}

/** "writes ~/.halo/config.json (workflows.enabled)" or the lineup's file, for the confirm card. */
export function writesLine(b: Board | null): string {
  if (!b || !b.lineup || b.lineup === "auto") return "writes: ~/.halo/config.json, the key workflows.enabled";
  return `writes: lineup ${b.lineup}'s file, its workflows: list`;
}
