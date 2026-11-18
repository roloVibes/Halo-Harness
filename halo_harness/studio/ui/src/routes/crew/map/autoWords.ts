// Agents -> 3 · Map on Auto (3.6.0.5 A11, A14, A22; the design's M1): Auto has no plan to edit, so its tab draws main
// alone and one line (AutoPlan.tsx). Its {names} are the API's `hand_to` (GET crew/map/auto: the agents a NEW session on
// Auto gets now, the seven that ship with Halo first). Pure: node runs it (tests/test_auto_name_ui.py).
import type { QuietOn } from "./quietOf";
import { isAuto } from "./truthWords";

const SHOWN = 12; // M1 names twelve, then "and {n} more"

/** M1 up to its button: the agents main can hand work to. */
export function m1Head(names: string[]): string {
  const list = names.slice(0, SHOWN).join(", ") + (names.length > SHOWN ? ` and ${names.length - SHOWN} more` : "");
  return `Auto has no plan to edit: main picks who works on each task as it goes, and Live draws each task as a named group. Main can hand work to: ${list}.`;
}
export const WATCH = "Watch it in Live";
export const M1_TAIL = "· + New map makes a map of your own.";
/** A14: M1 with no session on Auto, in place of [Watch it in Live]. */
export const NOTHING_ON_AUTO = "Nothing runs on Auto right now.";

/** A14: the session M1's [Watch it in Live] picks: the first of `on` (openOn's list, newest first) on Auto; "" for none. */
export const autoWatch = (on: QuietOn[]): string => on.find((s) => isAuto(s.a))?.sid || "";

/** A11: a map nothing on the Map tab may change (mapStore's `locked` = his Lock or this): Auto. */
export const readOnly = (name: string, scope = ""): boolean => isAuto(name, scope);
