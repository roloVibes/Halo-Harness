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
// 3.3.11.0 R3: an enabled pack's own blocks are steps too (`pack:<id>:<block>`, packSetup.ts): behind the core step
// their `after` names, else after the core steps, before the Summary; done once saved, run green, read or skipped.
import { createStore, useStore } from "../../lib/store";
import { lastCheckWord } from "./checkStore";
import { blockDone, blockOf, blockWord, isPackStep, placeSteps } from "./packSetup";
import { providersSet, setup, type SetupData } from "./store";

export type CoreStep = "providers" | "local" | "model" | "permissions" | "theme" | "team" | "linux" | "check" | "summary";
export type StepId = CoreStep | `pack:${string}`;
export type StepState = "current" | "done" | "todo";

const ORDER: CoreStep[] = ["providers", "local", "model", "permissions", "theme", "team", "linux", "check", "summary"];

export const TITLES: Record<CoreStep, string> = {
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
export const HELP_KEY: Record<CoreStep, string> = {
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

/** 3.3.11.0 R3: a step's name -- a core step's, or a pack block's title. */
export function titleOf(d: SetupData | null, s: StepId): string {
  if (!isPackStep(s)) return TITLES[s as CoreStep];
  return blockOf(d, s)?.block.title || s.split(":")[2] || s;
}

/** A door's word (studio/setup_door.py BLOCKS, plus `summary`) as a step; `roles` is the Team block's old name;
 *  3.3.11.0 R3: `pack:<id>:<block>`, a pack's block. */
export function stepOf(word: string): StepId | null {
  const w = String(word || "").toLowerCase();
  if (w === "roles") return "team";
  if (/^pack:[a-z][a-z0-9-]*:[a-z][a-z0-9_-]*$/.test(w)) return w as StepId;
  return (ORDER as string[]).includes(w) ? (w as StepId) : null;
}

/** The steps in the rail: Linux fixes only while this box needs them (or while it is the page open); 3.3.11.0 R3:
 *  the enabled packs' blocks placed among them (packSetup.ts placeSteps). */
export function stepsOf(d: SetupData | null, page: StepId): StepId[] {
  const core = ORDER.filter((s) => s !== "linux" || !!d?.linux_fixes.needed || page === "linux");
  return placeSteps(core, d) as StepId[];
}

export function lineupWord(d: SetupData): string {
  return d.team.active === "one-model" ? "one model for everything" : d.team.active + (d.team.source === "default" ? " (default)" : "");
}

/** Does step `s`'s block have what it needs. */
export function isDone(d: SetupData | null, s: StepId): boolean {
  if (!d) return false;
  if (isPackStep(s)) {
    const f = blockOf(d, s);
    return !!f && blockDone(f.block);
  }
  switch (s as CoreStep) {
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
      return stepsOf(d, "summary").every((x) => x === "summary" || (x === "linux" && !d.linux_fixes.needed) || isDone(d, x));
  }
  return false;
}

export function stateOf(d: SetupData | null, s: StepId, page: StepId): StepState {
  return s === page ? "current" : isDone(d, s) ? "done" : "todo";
}

/** What step `s` holds now, in a few words (the Summary's rows, the rail's tooltips). */
export function valueOf(d: SetupData | null, s: StepId): string {
  if (!d) return "reading the setup...";
  if (isPackStep(s)) {
    const f = blockOf(d, s);
    return f ? `${f.pack.name}: ${blockWord(f.block)}` : "not here (the pack is not enabled)";
  }
  switch (s as CoreStep) {
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
  return "";
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
  if (s && (!isPackStep(s) || blockOf(setup.get().data, s))) pages.update(() => ({ page: s })); // a pack's block: while it is here
}

export function step(by: 1 | -1): void {
  const page = pages.get().page;
  const list = stepsOf(setup.get().data, page);
  const i = list.indexOf(page) + by;
  if (i >= 0 && i < list.length) goto(list[i]);
}
