// The words and the clock of truth.ts (3.6.0.2 R19, R35, R41, decision 5), re-exported by it. WORDS is the ONE place the
// words live: the drawing of a run is Live, the line-by-line panel is Feed, the plan is Map. Another choice of words is an
// edit of this object (plus the tests' strings); every sentence and button label builds them from here. Pure.

export const WORDS = { live: "Live", feed: "Feed", map: "Map" } as const;
/** R35: the hovers of Session's two panels for this release, which swapped their names. */
export const WAS = { live: "(was Map)", feed: "(was Live)" } as const;

/** A line of the truth block or of a map line; a bracketed part of the design is a button (`act`, `label`), never text. */
export type Act = "new-session" | "watch-live" | "open-it" | "open-workflows" | "open-agents-live";
export type Line = { text: string; act?: Act; label?: string };

/** R41: the one locale-aware formatter for every {t} (epoch seconds; "" for no time); `secs`: with its seconds
 *  (3.6.0.14, the sheet's Last said). */
export const clock = (t: number, secs = false): string => (t
  ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", ...(secs ? { second: "2-digit" } : {}) }) : "");

/** 3.6.0.5 (decisions J1 M1): `auto`, `starter` and no map set are ONE map, the default, everywhere the page compares map
 *  names: the ONE test of a default's name (as crew/store.py is_auto). A session row carries no scope (it always ran the
 *  shipped default, A4); an open map passes its scope, so his old file named starter is NOT Auto. */
export const isAuto = (name?: string | null, scope = ""): boolean =>
  !!name && /^(auto|starter)$/i.test(name.trim()) && (!scope || scope === "starter");
/** His own old file named auto or starter (scope yours or project): listed under its own name, never in use (A4). */
export const isOldDefault = (name?: string | null, scope = ""): boolean =>
  !!name && /^(auto|starter)$/i.test(name.trim()) && !!scope && scope !== "starter";
/** Does a session whose map is `a` run on the map open as `name` (its `scope`)? */
export const onMap = (a: string | null, name: string, scope = ""): boolean =>
  isAuto(name, scope) ? isAuto(a) : !!a && !isAuto(a) && a === name;
/** The name a map is opened under: a default's name with no scope is Auto's own (`auto`), so a LAST of 3.6.0.x holding
 *  "starter", or `halo studio --edit map:starter`, opens and remembers Auto; his old file keeps its name. mapStore.ts
 *  exports it (openMap stores and remembers what it gives). */
export const openName = (name: string, scope = ""): string => (!scope && isAuto(name) ? "auto" : name);
/** {A} as a person reads it (R21): "Auto (the default)" when the session runs on the default, else the name. */
export const DEFAULT_MAP = "Auto (the default)";
export const mapName = (a: string, plain: boolean): string => (plain || isAuto(a) ? DEFAULT_MAP : a);
/** {B}: the map new sessions use, "Auto (the default)" when none is set (or it names the default). */
export const nextName = (b: string | null): string => (!b || isAuto(b) ? DEFAULT_MAP : b);
/** W16 (A6): a new map is never saved under a default's name; {name} exactly as he typed it (crew/store.py DEFAULT_NAME). */
export const nameOfTheDefault = (name: string): string => `${name} is a name of the default (Auto); give your map another name.`;
/** The coordinator's ruling (P4 batch 10): new sessions with no map (roles off, crew.map unset), the same string as
 *  crew/map_facts.py NOTE_NEXT_NONE (tests/test_map_s13_three_places.py holds the two equal). */
export const NEXT_NONE = "New sessions will run with no map.";
/** T10 when new sessions get no map (accepted as written, P4 batch 12). */
export const T10_NONE = "New session from Studio, no message yet. It will run with no map.";
/** A door to a panel the section no longer has (lib/workspace/persist.ts; accepted as written, P4 batch 12). */
export const NOT_HERE = "That panel is not on this page any more: there is nothing to open.";
/** P8 (judge B M5): how a workflow gets on a map, the ONE sentence 2 · Workflows says it in (its list with nothing on a
 *  map, the form of one on no map, the line after Save); the Map tab shipped in 3.6.0.0. */
export const TO_A_MAP = `To put a workflow on a map: in 3 · ${WORDS.map}, drag it from Agents and workflows onto a box, and that box hands work to it.`;
/** R11: the slot under Session's drawing when {n} boxes wait wholly below it (a press scrolls one row). */
export const moreBelow = (n: number): string => `↓ ${n} more below`;
