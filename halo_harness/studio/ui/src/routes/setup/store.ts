// The Setup section's store (3.3.0.0 R1): `GET setup/state` read once and
// again whenever config.json or a lineup moves on disk (`files_changed`: a
// `halo config set` in a terminal, another Studio, the wizard), each block's
// pick (what its Save writes, kept apart from what is saved, so a change on
// disk never loses one), and each block's last answer (the lines the server
// said, or its problems). Every Save posts through `act` (the Pack Manager's
// shape, routes/packs/manager/store.ts) and the answer is the fresh state.
import { api, ApiError } from "../../lib/api";
import { onFilesChanged } from "../../lib/filesLive";
import { createStore, setSectionStatus, toast, useStore } from "../../lib/store";

export type ThemeRow = { name: string; palette: Record<string, string> };
export type ModeRow = { id: string; label: string; note: string };
export type LineupRow = { name: string; label: string; scope: string; description: string; active: boolean; default: boolean };
export type ModelRow = { ref: string; provider: string; label: string; best_at: string; price: string; context: string };
export type SetupData = {
  model: string;
  permission_mode: string;
  theme: string;
  theme_default: string;
  themes: ThemeRow[];
  permission_modes: ModeRow[];
  team: { active: string; source: string; roles_enabled: boolean; lineups: LineupRow[] };
  models: ModelRow[];
  providers: Record<string, { set: boolean }>;
  linux_fixes: { needed: boolean; items: unknown[] };
  last_check: unknown;
};

/** The blocks that save something this round, by the key their Save writes. */
export type BlockId = "model" | "permission_mode" | "theme" | "team";
export type Answer = { ok: boolean; lines: string[] };

export type SetupState = {
  data: SetupData | null;
  loaded: boolean;
  error: string;
  busy: BlockId | "";
  picks: Partial<Record<BlockId, string>>;
  last: Partial<Record<BlockId, Answer>>;
};

/** A stable empty list for selectors (a new [] per read would redraw forever). */
export const NONE: never[] = [];

export const setup = createStore<SetupState>({ data: null, loaded: false, error: "", busy: "", picks: {}, last: {} });

export function useSetup<S>(select: (s: SetupState) => S): S {
  return useStore(setup, select);
}

/** What block `b` has saved now ("" when config.json has nothing). */
export function savedOf(d: SetupData | null, b: BlockId): string {
  if (!d) return "";
  return b === "team" ? d.team.active : d[b];
}

/** The value block `b` shows: its pick, else what is saved (the theme: the default when none is). */
export function shownOf(s: SetupState, b: BlockId): string {
  const pick = s.picks[b];
  if (pick !== undefined) return pick;
  const saved = savedOf(s.data, b);
  return b === "theme" ? saved || s.data?.theme_default || "" : saved;
}

export function changed(s: SetupState, b: BlockId): boolean {
  const pick = s.picks[b];
  return pick !== undefined && pick !== savedOf(s.data, b);
}

/** The block's own line: "saved", "1 changed" or "problem" (its last answer refused). */
export function blockWord(s: SetupState, b: BlockId): "saved" | "1 changed" | "problem" {
  if (s.last[b] && !s.last[b]!.ok) return "problem";
  return changed(s, b) ? "1 changed" : "saved";
}

export const providersSet = (d: SetupData | null) => Object.entries(d?.providers || {}).filter(([, v]) => v.set).map(([k]) => k);

function status(d: SetupData): void {
  const set = providersSet(d);
  setSectionStatus("setup", `${set.length ? set.join(", ") : "no provider"} · ${d.model || "no default model"} · lineup ${d.team.active}`);
}

let started = false;
let loading: Promise<void> | null = null;

export async function loadSetup(): Promise<void> {
  if (loading) return loading;
  loading = (async () => {
    try {
      const data = await api.get<SetupData>("setup/state");
      setup.update(() => ({ data, loaded: true, error: "" }));
      status(data);
    } catch (e) {
      setup.update(() => ({ loaded: true, error: e instanceof Error ? e.message : String(e) }));
    } finally {
      loading = null;
    }
  })();
  return loading;
}

/** Start once (the section's view or a panel): the first read and the files watcher. */
export function startSetup(): void {
  if (started) return;
  started = true;
  onFilesChanged(["config", "lineups"], () => void loadSetup());
  void loadSetup();
}

export function pick(b: BlockId, value: string): void {
  setup.update((s) => ({ picks: { ...s.picks, [b]: value }, last: { ...s.last, [b]: undefined } }));
}

export function revert(b: BlockId): void {
  setup.update((s) => {
    const picks = { ...s.picks };
    delete picks[b];
    return { picks, last: { ...s.last, [b]: undefined } };
  });
}

/** POST one block's Save; the answer is the fresh state and the lines it wrote (or its problems). */
export async function act(path: string, body: Record<string, unknown>, block: BlockId): Promise<boolean> {
  setup.update(() => ({ busy: block }));
  try {
    const r = await api.post<SetupData & { lines?: string[] }>(path, body);
    const { lines, ...data } = r;
    setup.update((s) => {
      const picks = { ...s.picks };
      delete picks[block];
      return { data: data as SetupData, picks, last: { ...s.last, [block]: { ok: true, lines: lines || [] } } };
    });
    status(data as SetupData);
    toast(lines?.[0] || "Saved", "done", 4000);
    return true;
  } catch (e) {
    const lines = e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)];
    setup.update((s) => ({ last: { ...s.last, [block]: { ok: false, lines } } }));
    toast(lines[0], "error", 6000);
    return false;
  } finally {
    setup.update(() => ({ busy: "" }));
  }
}

/** Save block `b`'s pick: the team through `setup/team`, the three config keys through `setup/config`. */
export function save(b: BlockId): Promise<boolean> {
  const value = shownOf(setup.get(), b);
  return b === "team" ? act("setup/team", { lineup: value }, b) : act("setup/config", { key: b, value }, b);
}
