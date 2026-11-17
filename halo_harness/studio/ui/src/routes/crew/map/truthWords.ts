// The words and the clock of truth.ts (3.6.0.2 R19, R35, R41, decision 5), re-exported by it. WORDS is the ONE place the
// words live: the drawing of a run is Live, the line-by-line panel is Feed, the plan is Map. Another choice of words is an
// edit of this object (plus the tests' strings); every sentence and button label builds them from here. Pure.

export const WORDS = { live: "Live", feed: "Feed", map: "Map" } as const;
/** R35: the hovers of Session's two panels for this release, which swapped their names. */
export const WAS = { live: "(was Map)", feed: "(was Live)" } as const;

/** A line of the truth block or of a map line; a bracketed part of the design is a button (`act`, `label`), never text. */
export type Act = "new-session" | "watch-live" | "open-it" | "open-workflows" | "open-agents-live";
export type Line = { text: string; act?: Act; label?: string };

/** R41: the one locale-aware formatter for every {t} (epoch seconds; "" for no time). */
export const clock = (t: number): string => (t ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

/** {A} as a person reads it (R21): "starter (the default)" when the session took starter by default, else the name. */
export const DEFAULT_MAP = "starter (the default)";
export const mapName = (a: string, plain: boolean): string => (plain ? DEFAULT_MAP : a);
/** {B}: the map new sessions use, "starter (the default)" when none is set. */
export const nextName = (b: string | null): string => b || DEFAULT_MAP;
/** The coordinator's ruling (P4 batch 10): new sessions with no map (roles off, crew.map unset), the same string as
 *  crew/map_facts.py NOTE_NEXT_NONE (tests/test_map_s13_three_places.py holds the two equal). */
export const NEXT_NONE = "New sessions will run with no map.";
/** R11: the slot under Session's drawing when {n} boxes wait wholly below it (a press scrolls one row). */
export const moreBelow = (n: number): string => `↓ ${n} more below`;
