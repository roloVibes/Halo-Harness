// Setup's pages (3.3.1.0 R1): the terminal wizard's steps in its order, one
// block per page -- Providers, Local models, Default model, Permissions,
// Theme, Team, Linux fixes (a step only while this box needs them, or while
// it is the page open), Check, Summary. Which page is open is this store:
// the rail jumps anywhere, Back / Next walk the list, `?block=<id>` (the door)
// opens one, and the page last open is remembered for this home
// (localStorage under the state's `home` hash; `?block=` wins). A step is
// "done" when its block has what it needs: a provider set; nothing for Local
// models; a model picked; a mode; a theme; a lineup or auto; the fixes
// applied; a check run once. The Summary is done when every other step is.
import { createStore, useStore } from "../../lib/store";
import { lastCheckWord } from "./checkStore";
import { providersSet, setup, type SetupData } from "./store";

export type StepId = "providers" | "local" | "model" | "permissions" | "theme" | "team" | "linux" | "check" | "summary";
export type StepState = "current" | "done" | "todo";

const ORDER: StepId[] = ["providers", "local", "model", "permissions", "theme", "team", "linux", "check", "summary"];

export const TITLES: Record<StepId, string> = {
  providers: "Providers",
  local: "Local models",
  model: "Default model",
  permissions: "Permissions",
  theme: "Theme",
  team: "Team",
  linux: "Linux fixes",
  check: "Check",
  summary: "Summary",
};

/** Each step's block by its help key (routes/help-setup.ts): its one-line `about` and its `help` lines. */
export const HELP_KEY: Record<StepId, string> = {
  providers: "setup-providers",
  local: "setup-local",
  model: "setup-model",
  permissions: "setup-permissions",
  theme: "setup-theme",
  team: "setup-team",
  linux: "setup-linux",
  check: "setup-check",
  summary: "setup-summary",
};

/** A door's word (studio/setup_door.py BLOCKS, plus `summary`) as a step; `roles` is the Team block's old name. */
export function stepOf(word: string): StepId | null {
  const w = String(word || "").toLowerCase();
  if (w === "roles") return "team";
  return (ORDER as string[]).includes(w) ? (w as StepId) : null;
}

/** The steps in the rail: Linux fixes only while this box needs them (or while it is the page open). */
export function stepsOf(d: SetupData | null, page: StepId): StepId[] {
  return ORDER.filter((s) => s !== "linux" || !!d?.linux_fixes.needed || page === "linux");
}

export function lineupWord(d: SetupData): string {
  return d.team.active === "one-model" ? "one model for everything" : d.team.active + (d.team.source === "default" ? " (default)" : "");
}

/** Does step `s`'s block have what it needs. */
export function isDone(d: SetupData | null, s: StepId): boolean {
  if (!d) return false;
  switch (s) {
    case "providers":
      return providersSet(d).length > 0;
    case "local":
      return true;
    case "model":
      return !!d.model;
    case "permissions":
      return !!d.permission_mode;
    case "theme":
      return !!d.theme;
    case "team":
      return !!d.team.active;
    case "linux":
      return !d.linux_fixes.needed;
    case "check":
      return !!d.last_check?.when;
    case "summary":
      return ORDER.every((x) => x === "summary" || (x === "linux" && !d.linux_fixes.needed) || isDone(d, x));
  }
}

export function stateOf(d: SetupData | null, s: StepId, page: StepId): StepState {
  return s === page ? "current" : isDone(d, s) ? "done" : "todo";
}

/** What step `s` holds now, in a few words (the Summary's rows, the rail's tooltips). */
export function valueOf(d: SetupData | null, s: StepId): string {
  if (!d) return "reading the setup...";
  switch (s) {
    case "providers": {
      const set = providersSet(d);
      return set.length ? set.join(", ") : "no provider set";
    }
    case "local": {
      const n = d.local_models.model_dirs.length;
      return `${n} folder${n === 1 ? "" : "s"} · runtime ${d.local_models.runtime || "not set"}`;
    }
    case "model":
      return d.model || "not set";
    case "permissions":
      return d.permission_mode || "not set";
    case "theme":
      return d.theme || `${d.theme_default} (default)`;
    case "team":
      return lineupWord(d);
    case "linux":
      return d.linux_fixes.needed ? `${d.linux_fixes.items.length} to apply` : "nothing to fix";
    case "check":
      return lastCheckWord(d.last_check);
    case "summary":
      return "";
  }
}

// -- which page is open ----------------------------------------------------------------------------------------
const KEY = "halo.studio.setup.page.";

type Pages = { page: StepId; chosen: boolean };
export const pages = createStore<Pages>({ page: "providers", chosen: false });

export function usePage(): StepId {
  return useStore(pages, (s) => s.page);
}

function remember(page: StepId): void {
  const home = setup.get().data?.home;
  if (!home) return;
  try {
    localStorage.setItem(KEY + home, page);
  } catch {
    /* a browser that keeps nothing: the page opens on Providers next time */
  }
}

/** Open step `s`'s page (the rail, Back / Next, a Change jump, the door). */
export function goto(s: StepId): void {
  pages.update(() => ({ page: s, chosen: true }));
  remember(s);
}

/** The state arrived (its `home` with it): the page last open for this home, unless one was chosen already. */
export function adoptRemembered(home: string): void {
  if (!home) return;
  if (pages.get().chosen) return remember(pages.get().page);
  let saved = "";
  try {
    saved = localStorage.getItem(KEY + home) || "";
  } catch {
    saved = "";
  }
  const s = stepOf(saved);
  if (s) pages.update(() => ({ page: s }));
}

export function step(by: 1 | -1): void {
  const page = pages.get().page;
  const list = stepsOf(setup.get().data, page);
  const i = list.indexOf(page) + by;
  if (i >= 0 && i < list.length) goto(list[i]);
}
