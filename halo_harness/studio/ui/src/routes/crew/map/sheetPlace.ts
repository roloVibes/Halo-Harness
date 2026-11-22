// Where the box's sheet goes, and the room its head holds (3.6.0.14 OP1, rules O1-1 and O1-4). The sheet is the step-in
// card (StepIn.tsx) placed at the box it opened from:
// - Agents -> Live: 440 wide, its top-left at the anchor's (its top-right when 440 would pass the view's right less 8),
//   as tall as its words at open but at most the view less 16, lifted till its bottom is 8 inside the view;
// - Session's drawer: the drawer less 16 wide at left 8; 6 px under its box when 240 fit below (its bottom 8 inside),
//   else 6 px over it when 240 fit above (its top 8 inside), else today's place (40 from the frame's foot, at most the
//   drawer less 56: the drawing's scroll box can be far lower than the drawer).
// With no anchor at all (a line in the drawer that is not into a group, an element gone or flat) Agents puts it at the
// view's top-right, 8 inside, and the drawer at today's place. An anchor partly out of view is clamped 8 inside. Every
// rect is downFit.ts's `Rect`, in the px of the frame the sheet is absolute in. Called ONCE, at open: never re-placed.
// The head (O1-4): the state line holds the rows of its longest state ("waiting on you") and NOW two rows (nowRoom.ts,
// the held form), so nothing in the head moves while the sheet is open. Pure: no React, no DOM (tests/test_sheet_place.py).
import type { Rect } from "../../session/downFit";
import { STATE_WORDS } from "./groupWords";
import { nowFit, rowsOf } from "./nowRoom";

export type Side = "corner" | "right" | "below" | "above" | "fixed";
export type Place = { left: number; top: number; width: number; height: number; side: Side };

export const SHEET_W = 440;
export const EDGE = 8;
export const GAP = 6;
export const ROOM = 240;
export const FOOT = 40;
export const FIXED_LESS = 56;

const wide = (r: Rect): number => r.right - r.left;
const tall = (r: Rect): number => r.bottom - r.top;

/** Agents -> Live: the sheet at its anchor's top-left corner (top-right near the view's right), `h` its words' height. */
export function agentsPlace(anchor: Rect | null, view: Rect, h: number): Place {
  const width = Math.min(SHEET_W, wide(view) - 2 * EDGE);
  const height = Math.max(0, Math.min(h, tall(view) - 2 * EDGE));
  if (!anchor) return { left: view.right - EDGE - width, top: view.top + EDGE, width, height, side: "fixed" };
  const turn = anchor.left + width > view.right - EDGE;
  let left = turn ? Math.min(anchor.right, view.right - EDGE) - width : anchor.left;
  left = Math.max(left, view.left + EDGE);
  let top = anchor.top;
  if (top + height > view.bottom - EDGE) top = view.bottom - EDGE - height;
  top = Math.max(top, view.top + EDGE);
  return { left, top, width, height, side: turn ? "right" : "corner" };
}

/** Session's drawer: 6 px under its box, else over it, else today's place; `frame` the `.mp-down` the sheet sits in. */
export function drawerPlace(anchor: Rect | null, view: Rect, frame: { width: number; height: number }, h: number): Place {
  const left = EDGE, width = frame.width - 2 * EDGE;
  if (anchor) {
    const top = Math.max(anchor.bottom + GAP, view.top + EDGE);
    const below = view.bottom - EDGE - top;
    if (below >= ROOM) return { left, top, width, height: Math.min(h, below), side: "below" };
    const foot = Math.min(anchor.top - GAP, view.bottom - EDGE);
    const above = foot - (view.top + EDGE);
    if (above >= ROOM) {
      const height = Math.min(h, above);
      return { left, top: foot - height, width, height, side: "above" };
    }
  }
  const height = Math.max(0, Math.min(h, frame.height - FIXED_LESS)); // today's place is the drawer's, its room too
  return { left, top: frame.height - FOOT - height, width, height, side: "fixed" };
}

/** The selector of the element a sheet opens at, from the target's id (stepInTarget.ts hitId); null: no anchor. `esc`:
 *  CSS.escape in the browser. A line into a group opens at that group's box (its sheet is the group's card); any other
 *  line at its label, which only Agents draws. */
export function anchorSel(id: string, esc: (s: string) => string = (s) => s): string | null {
  const box = (b: string) => `[data-box="${esc(b)}"]`;
  const flow = (w: string) => `[data-box][data-workflow="${esc(w)}"]`;
  if (id.startsWith("member:")) return `[data-member="${esc(id.slice(7))}"]`;
  if (id.startsWith("box:")) return box(id.slice(4));
  if (id.startsWith("group:")) return box(id);
  if (id.startsWith("head:")) return flow(id.slice(5));
  if (id.startsWith("step:")) {
    const rest = id.slice(5), cut = rest.lastIndexOf(":");
    return cut > 0 ? flow(rest.slice(0, cut)) : null;
  }
  if (id.startsWith("line:")) {
    const rest = id.slice(5), cut = rest.indexOf(">");
    if (cut <= 0) return null;
    const from = rest.slice(0, cut), to = rest.slice(cut + 1);
    return to.startsWith("group:") ? box(to) : `.mp-label[data-from="${esc(from)}"][data-to="${esc(to)}"]`;
  }
  return null;
}

/** The sheet's text width: its 1 px borders and 8 px padding. */
export const textWidth = (width: number): number => width - 18;

/** The state line's held rows: the words at the click, and the same words with their last part the longest state
 *  ("waiting on you"), so a state word that changes while the sheet is open never adds a row. */
export function stateHeld(text: string, tw: number): number {
  const cut = text.lastIndexOf(" · ");
  const waiting = cut >= 0 ? `${text.slice(0, cut)} · ${STATE_WORDS.waiting}` : STATE_WORDS.waiting;
  return Math.max(rowsOf(text, "", tw), rowsOf(waiting, "", tw));
}

export type Head = { stateRows: number; nowRows: number; text: string; secs: string };
/** The head of a sheet `width` wide: the state line `text`'s held rows, and NOW in two held rows (the sheet holds its
 *  drawing: longer words read the held form "a tool · {s}"). */
export function sheetHead(width: number, text: string, now: { text: string; secs: string }): Head {
  const tw = textWidth(width);
  const fit = nowFit(now, tw, { rows: 2, grown: false }, true);
  return { stateRows: stateHeld(text, tw), nowRows: fit.rows, text: fit.text, secs: fit.secs };
}

/** O1-2: what an event does to an open sheet. `at`: where it lands -- the sheet, a `.scrim` (the Stop confirm), the
 *  drawing's slot, a pick target of this drawing (a box, a member, a line's label or hit path), the drawing's empty
 *  part (`pan`), anywhere else; `field`: a text field has the key. "pick": nothing here, the click's pick opens that
 *  box's sheet (or closes this one when it is the same). A pointer-down on the slot folds nothing: its own press folds
 *  the sheet first (R4). A wheel reaches the sheet only over the drawing; over the sheet it scrolls the body. */
export type SheetEvent = { kind: "pointer" | "key" | "wheel" | "zoom"; at: "sheet" | "scrim" | "slot" | "pick" | "pan" | "else";
  key?: string; field?: boolean };
export function sheetClose(e: SheetEvent): "none" | "pick" | "fold" {
  if (e.kind === "zoom") return "fold";
  if (e.kind === "key") return e.key === "Escape" && !e.field ? "fold" : "none";
  if (e.kind === "wheel") return e.at === "pan" || e.at === "pick" ? "fold" : "none";
  if (e.at === "sheet" || e.at === "scrim" || e.at === "slot") return "none";
  return e.at === "pick" ? "pick" : "fold";
}

export type Inset = { top: number; right: number; bottom: number; left: number };
const clamp = (v: number, hi: number): number => Math.max(0, Math.min(hi, v));
/** O1-2: the insets that cut `sheet` down to its box's rectangle `anchor` (the unfold's start), each 0..the sheet's size. */
export function fromInset(sheet: Place, anchor: Rect): Inset {
  return { top: clamp(anchor.top - sheet.top, sheet.height), right: clamp(sheet.left + sheet.width - anchor.right, sheet.width),
    bottom: clamp(sheet.top + sheet.height - anchor.bottom, sheet.height), left: clamp(anchor.left - sheet.left, sheet.width) };
}
export const insetOf = (i: Inset): string => `inset(${i.top}px ${i.right}px ${i.bottom}px ${i.left}px)`;

/** O1-6: the sheet opens when the one GET of what its agent said answers, or at 1 s. */
export const SAID_WAIT_MS = 1000;
export const saidOpen = (answered: boolean, waitedMs: number): boolean => answered || waitedMs >= SAID_WAIT_MS;
