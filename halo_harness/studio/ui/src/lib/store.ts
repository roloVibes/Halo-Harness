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

export type SectionId = "orchestra" | "roles" | "org" | "design" | "flow";
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
};

export type ToastItem = { id: number; text: string; tone: "done" | "error" | "info" };

export type PanelRef = { section: SectionId; panel: string };

export type StudioState = {
  section: SectionId;
  visited: SectionId[];
  theme: ThemeChoice;
  paletteOpen: boolean;
  railOpen: boolean;
  inspector: PanelRef | null;
  feed: { status: FeedStatus; events: number; lastKind: string; lastTs: number; sessions: SessionInfo[] };
  activity: Partial<Record<SectionId, number>>;
  toasts: ToastItem[];
};

export const SECTION_IDS: SectionId[] = ["orchestra", "roles", "org", "design", "flow"];

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

function initialSection(): SectionId {
  const asked = /[?&]mode=(orchestra|roles|org|design|flow)\b/.exec(location.search);
  if (asked) return asked[1] as SectionId;
  const saved = readLocal("halo.studio.section") || readLocal("halo-studio-mode");
  return (SECTION_IDS as string[]).includes(saved) ? (saved as SectionId) : "roles";
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
  feed: { status: "off", events: 0, lastKind: "", lastTs: 0, sessions: [] },
  activity: {},
  toasts: [],
});

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

export function markActivity(section: SectionId): void {
  studio.update((s) => ({ activity: { ...s.activity, [section]: Date.now() } }));
}
