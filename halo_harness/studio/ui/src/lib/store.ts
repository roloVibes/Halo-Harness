// A tiny external store (no library): `createStore(initial)` gives get / set /
// update / subscribe, and `useStore(store, selector)` reads a slice through
// React's useSyncExternalStore. `studio` is the shell's one app store.
import { useSyncExternalStore } from "react";

export type Store<T> = {
  get: () => T;
  set: (next: T) => void;
  update: (fn: (prev: T) => Partial<T>) => void;
  subscribe: (fn: () => void) => () => void;
};

export function createStore<T extends object>(initial: T): Store<T> {
  let state = initial;
  const subs = new Set<() => void>();
  const emit = () => subs.forEach((fn) => fn());
  return {
    get: () => state,
    set(next) {
      if (next !== state) {
        state = next;
        emit();
      }
    },
    update(fn) {
      const patch = fn(state);
      if (Object.keys(patch).length) {
        state = { ...state, ...patch };
        emit();
      }
    },
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
  };
}

export function useStore<T extends object, S>(store: Store<T>, select: (s: T) => S): S {
  return useSyncExternalStore(store.subscribe, () => select(store.get()), () => select(store.get()));
}

// -- the shell's state -----------------------------------------------------------

export type CoreSectionId = "orchestra" | "roles" | "design" | "fleet" | "team" | "session" | "packs"; // packs: 3.2.0.0 R6
/** 3.2.0.0 R3: a pack's own section, `<pack id>--<section id>` (routes/packs: the registry the server builds). */
export type PackSectionId = `${string}--${string}`;
export type SectionId = CoreSectionId | PackSectionId;
export type ThemeChoice = "auto" | "dark" | "light";
export type FeedStatus = "off" | "connecting" | "open" | "retrying" | "down";

export type SessionInfo = {
  session_id: string;
  title?: string;
  mode?: string;
  kind?: string;
  cwd?: string;
  started?: number;
  pid?: number;
  /** From GET sessions (the control socket's status): waiting | busy | idle | unknown. */
  status?: string;
  busy?: boolean;
  pending?: Partial<Record<"permission" | "question" | "plan" | "approval", string[]>> | null;
  model?: string | null;
  /** 3.0.5.0 Fleet: sub-agents queued, running, waiting or paused right now. */
  agents?: number | null;
  harness?: { id?: string; name?: string; host?: string; user?: string; version?: string; os?: string } | null;
  project?: { root?: string; repo?: string | null; branch?: string | null; dirty?: boolean | null } | null;
  parent?: string | null;
};

export type ToastItem = { id: number; text: string; tone: "done" | "error" | "info" };

export type PanelRef = { section: SectionId; panel: string };

/** The "How this works" overlay: which section, and whether it is the first-visit welcome. */
export type HelpRef = { section: SectionId; welcome: boolean };

export type StudioState = {
  section: SectionId;
  visited: SectionId[];
  theme: ThemeChoice;
  paletteOpen: boolean;
  railOpen: boolean;
  inspector: PanelRef | null;
  help: HelpRef | null;
  /** A section's own status line (3.0.7.0 R2: Roles and Design each set theirs from their store). */
  status: Partial<Record<SectionId, string>>;
  feed: { status: FeedStatus; events: number; lastKind: string; lastTs: number; sessions: SessionInfo[] };
  activity: Partial<Record<SectionId, number>>;
  toasts: ToastItem[];
};

/** Every section id, in the tab order (routes/index.tsx SECTIONS is the order; store.ts cannot import it). */
export const SECTION_IDS: CoreSectionId[] = ["session", "team", "roles", "fleet", "design", "orchestra", "packs"];

function readLocal(key: string): string {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

export function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private window: nothing remembered */
  }
}

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

/** `?mode=` wins, then the section saved for this browser (a pack's own when the page names it, 3.2.1.0 R1);
 *  nothing saved: Session while a session is live here, else Roles. */
function initialSection(): SectionId {
  const asked = /[?&]mode=(orchestra|roles|design|fleet|team|session|packs)\b/.exec(location.search); // packs: 3.2.0.0 R7
  if (asked) return asked[1] as SectionId;
  const saved = readLocal("halo.studio.section") || readLocal("halo-studio-mode");
  if ((SECTION_IDS as string[]).includes(saved)) return saved as SectionId;
  if (saved.includes("--") && bootPackSections().some((s) => s.id === saved)) return saved as SectionId;
  return bootLiveSession() ? "session" : "roles";
}

function initialTheme(): ThemeChoice {
  const saved = readLocal("halo.studio.theme");
  return saved === "dark" || saved === "light" || saved === "auto" ? saved : "dark";
}

const first = initialSection();

export const studio = createStore<StudioState>({
  section: first,
  visited: [first],
  theme: initialTheme(),
  paletteOpen: false,
  railOpen: readLocal("halo.studio.rail") !== "closed",
  inspector: null,
  help: null,
  status: {},
  feed: { status: "off", events: 0, lastKind: "", lastTs: 0, sessions: [] },
  activity: {},
  toasts: [],
});

// -- "How this works": the overlay and the first-visit welcome ------------------
export const SEEN_PREFIX = "halo.studio.seen.";
/** `?tour=off` (captures, tests) keeps the first-visit welcome shut, as on the classic page; so does `?edit=` (3.1.1.0 R3). */
const NO_WELCOME = typeof location !== "undefined" && /[?&](tour=off\b|edit=)/.test(location.search);

export function openHelp(section: SectionId, welcome = false): void {
  studio.update(() => ({ help: { section, welcome }, paletteOpen: false }));
}

/** Close the overlay; the section counts as seen, so its welcome does not come back. */
export function closeHelp(): void {
  const help = studio.get().help;
  if (help) writeLocal(SEEN_PREFIX + help.section, "1");
  studio.update(() => ({ help: null }));
}

/** The first time a section shows in this browser: its welcome card. */
export function welcomeIfNew(section: SectionId): void {
  if (NO_WELCOME || studio.get().help || readLocal(SEEN_PREFIX + section)) return;
  openHelp(section, true);
}

export function goSection(section: SectionId): void {
  writeLocal("halo.studio.section", section);
  studio.update((s) => ({ section, visited: s.visited.includes(section) ? s.visited : [...s.visited, section], inspector: null }));
}

export function setTheme(theme: ThemeChoice): void {
  writeLocal("halo.studio.theme", theme);
  document.documentElement.dataset.theme = theme;
  studio.update(() => ({ theme }));
}

export function cycleTheme(): void {
  const order: ThemeChoice[] = ["dark", "light", "auto"];
  setTheme(order[(order.indexOf(studio.get().theme) + 1) % order.length]);
}

export function toggleRail(): void {
  const railOpen = !studio.get().railOpen;
  writeLocal("halo.studio.rail", railOpen ? "open" : "closed");
  studio.update(() => ({ railOpen }));
}

let toastSeq = 0;
export function toast(text: string, tone: ToastItem["tone"] = "info", ms = 3200): void {
  const id = ++toastSeq;
  studio.update((s) => ({ toasts: [...s.toasts.slice(-3), { id, text, tone }] }));
  window.setTimeout(() => studio.update((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), ms);
}

/** A section's line in the status bar (setSectionStatus("roles", "...")). */
export function setSectionStatus(section: SectionId, text: string): void {
  studio.update((s) => (s.status[section] === text ? {} : { status: { ...s.status, [section]: text } }));
}

export function markActivity(section: SectionId): void {
  studio.update((s) => ({ activity: { ...s.activity, [section]: Date.now() } }));
}
