// A tiny external store (no library): `createStore(initial)` gives get / set /
// update / subscribe, and `useStore(store, selector)` reads a slice through
// React's useSyncExternalStore. `studio` is the shell's one app store.
import { useSyncExternalStore } from "react";
import { bootLiveSession, bootNoProvider } from "./boot";
import { askedSection, sectionFor } from "./sectionStart";
export { bootLiveSession, bootNoProvider, bootPackSections, type BootPackSection } from "./boot";

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

// packs: 3.2.0.0 R6; setup: 3.3.0.0 R1; settings: 3.3.3.0 R2; local: 3.3.5.0 R1; 3.3.13.0 R2: design is the design pack's
export type CoreSectionId = "orchestra" | "roles" | "fleet" | "team" | "session" | "packs" | "setup" | "settings" | "local";
/** 3.2.0.0 R3: a pack's own section, `<pack id>--<section id>` (routes/packs: the registry the server builds). */
export type PackSectionId = `${string}--${string}`;
export type SectionId = CoreSectionId | PackSectionId;
/** 3.3.12.0 R1: a theme name of the palette registry (`holo`, `ember-daltonized`, ...) or "auto" (follow the system). */
export type ThemeChoice = string;
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

/** The "How this works" overlay: which section (3.3.2.0 R1: only ever opened by a click or a key). */
export type HelpRef = { section: SectionId; part?: string }; // 3.3.2.0 R2: `part` scrolls to one part ("moving": Moving panels)

/** 3.3.2.0 R1: the left rail, icons only (56 px) or expanded with titles (248 px); Focus hides it whatever this says. */
export type RailMode = "icons" | "open";

export type StudioState = {
  section: SectionId;
  visited: SectionId[];
  theme: ThemeChoice;
  paletteOpen: boolean;
  rail: RailMode;
  /** 3.3.2.0 R1: Focus hides the rail, the inspector and the status bar (F, the header button, the palette). */
  focus: boolean;
  inspector: PanelRef | null;
  help: HelpRef | null;
  /** A section's own status line (3.0.7.0 R2: Roles and Design each set theirs from their store). */
  status: Partial<Record<SectionId, string>>;
  feed: { status: FeedStatus; events: number; lastKind: string; lastTs: number; sessions: SessionInfo[] };
  activity: Partial<Record<SectionId, number>>;
  toasts: ToastItem[];
};

/** Every section id, in the tab order (routes/index.tsx SECTIONS is the order; store.ts cannot import it). */
export const SECTION_IDS: CoreSectionId[] = ["session", "team", "roles", "fleet", "orchestra", "packs", "setup", "settings", "local"];

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

/** `?mode=` wins; then (3.3.0.0 R3) Setup while no provider is set up, whatever was saved; then the section saved
 *  for this browser (a pack's own when the page names it, 3.2.1.0 R1); nothing saved: Session while a session is
 *  live here, else Roles. */
let firstNote = ""; // 3.3.13.0 R2: `?mode=design` with the design pack off (lib/sectionStart.ts)

function initialSection(): SectionId {
  const asked = askedSection(SECTION_IDS);
  firstNote = asked.note;
  if (asked.section) return asked.section as SectionId;
  if (bootNoProvider()) return "setup";
  const saved = sectionFor(readLocal("halo.studio.section") || readLocal("halo-studio-mode"), SECTION_IDS);
  if (saved) return saved as SectionId;
  return bootLiveSession() ? "session" : "roles";
}

/** 3.3.12.0 R1: the theme the server painted the page in (`theme` in config.json, studio/theme_boot.py), else follow
 *  the system; lib/theme.ts reads the registry and keeps it in step with the key. */
function initialTheme(): ThemeChoice {
  try {
    return document.documentElement.dataset.theme || "auto";
  } catch {
    return "auto";
  }
}

const first = initialSection();

/** The section this page opened on (3.3.2.0 R1: the one section Start here may show over). */
export function firstSection(): SectionId {
  return first;
}

/** 3.3.2.0 R1: icons by default ("closed" from before reads as icons); `?rail=open` (drivers, captures) expands it
 *  for this page without remembering it. */
function initialRail(): RailMode {
  if (typeof location !== "undefined" && /[?&]rail=open\b/.test(location.search)) return "open";
  return readLocal("halo.studio.rail") === "open" ? "open" : "icons";
}

const INSPECTOR_KEY = "halo.studio.inspector";

/** 3.3.2.0 R1: the inspector this browser left open (a panel of the section the page opens on), else closed. */
function initialInspector(): PanelRef | null {
  try {
    const got = JSON.parse(readLocal(INSPECTOR_KEY) || "null") as PanelRef | null;
    return got && got.section === first && typeof got.panel === "string" ? got : null;
  } catch {
    return null;
  }
}

export const studio = createStore<StudioState>({
  section: first,
  visited: [first],
  theme: initialTheme(),
  paletteOpen: false,
  rail: initialRail(),
  focus: readLocal("halo.studio.focus") === "on",
  inspector: initialInspector(),
  help: null,
  status: {},
  feed: { status: "off", events: 0, lastKind: "", lastTs: 0, sessions: [] },
  activity: {},
  toasts: firstNote ? [{ id: -1, text: firstNote, tone: "info" }] : [], // 3.3.13.0 R2: `?mode=design`, its pack off
});
if (firstNote) window.setTimeout(() => studio.update((s) => ({ toasts: s.toasts.filter((t) => t.id !== -1) })), 9000);

// 3.3.2.0 R1: the inspector's open/closed choice, remembered per browser whatever opened or closed it
// (a panel's Settings, a Design artboard's knobs, its close button, Esc, a section switch).
let savedInspector = studio.get().inspector;
studio.subscribe(() => {
  const ref = studio.get().inspector;
  if (ref === savedInspector) return;
  savedInspector = ref;
  writeLocal(INSPECTOR_KEY, ref ? JSON.stringify(ref) : null);
});

// -- "How this works": opened by the ? button, the palette or `?`, never on its own --------------
// 3.3.2.0 R1: the first-visit welcome card is gone for every section (rolo, 2026-10-27: "the pop up is annoying
// when you open a tab"); a section opens on its own content and its help stays one click away.

export function openHelp(section: SectionId, part?: string): void {
  studio.update(() => ({ help: { section, part }, paletteOpen: false }));
}

export function closeHelp(): void {
  studio.update(() => ({ help: null }));
}

export function goSection(section: SectionId): void {
  writeLocal("halo.studio.section", section);
  studio.update((s) => ({ section, visited: s.visited.includes(section) ? s.visited : [...s.visited, section], inspector: null }));
}

/** 3.3.2.0 R1: the rail's chevron: icons <-> expanded (the titles; R2: nothing else). */
export function toggleRail(): void {
  const rail: RailMode = studio.get().rail === "open" ? "icons" : "open";
  writeLocal("halo.studio.rail", rail);
  studio.update(() => ({ rail, focus: false }));
  writeLocal("halo.studio.focus", null);
}

/** 3.3.2.0 R1: Focus on or off; off brings the rail and the inspector back as they were. */
export function toggleFocus(): void {
  const focus = !studio.get().focus;
  writeLocal("halo.studio.focus", focus ? "on" : null);
  studio.update(() => ({ focus }));
}

let toastSeq = 0;
/** 3.3.15.0 L1: a toast holds 4 s (lib/ui/Toast.tsx fades it out); an error stays until dismissed (its ✕). */
export function toast(text: string, tone: ToastItem["tone"] = "info", ms = 4000): void {
  const id = ++toastSeq;
  studio.update((s) => ({ toasts: [...s.toasts.slice(-3), { id, text, tone }] }));
  if (tone !== "error") window.setTimeout(() => studio.update((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), ms);
}

/** A section's line in the status bar (setSectionStatus("roles", "...")). */
export function setSectionStatus(section: SectionId, text: string): void {
  studio.update((s) => (s.status[section] === text ? {} : { status: { ...s.status, [section]: text } }));
}

export function markActivity(section: SectionId): void {
  studio.update((s) => ({ activity: { ...s.activity, [section]: Date.now() } }));
}
