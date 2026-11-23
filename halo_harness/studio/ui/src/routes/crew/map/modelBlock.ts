// The MODEL block's pure rules (3.6.0.15 O2-5, "the box acts"): what the sheet's MODEL block draws for the GET
// crew/agent-model's answer (studio/crew_model_api.py: {kind, name, model, first, line, can, now}) and for what a pick
// or Undo answered. No React, no DOM, no store: node runs it (tests/test_sheet_place.py), as sheetPlace.ts beside
// useSheet.ts; StepInModel.tsx draws it. The block is a member's sheet's (that helper), main's (MAIN) and, O2-9, a
// group's sheet's CHOSEN row's ("MODEL of {name}"); a workflow block's and a line label's sheet have none and ask nothing.

export type ModelAnswer = { kind: string; name: string; model: string; first: string; line: string; can: boolean; now: boolean };
/** "reading": the GET has not answered yet. */
export type ModelGot = ModelAnswer | { error: string } | "reading";
/** What the last pick or Undo answered: its line, and the pick's undo token (sent back as given). */
export type After = { line: string; undo: unknown | null };
export type BlockParts = { heading: string; label: string; first: string; rows: string[]; picker: boolean;
  /** the button's word, "" when it is not drawn */ edit: string; make: string; undo: string;
  /** controls hold still: the button row is drawn from the first draw whenever a button can be in it, and Undo's room is
   *  kept there (hidden) whenever a pick can bring it, so Undo's coming moves nothing */ btns: boolean; undoRoom: boolean };

/** The kinds a pick makes an agent of his from: [Make it an agent] is offered for these. */
export const MADE = ["SHIPPED", "ROUTED", "BUILT-IN", "MADE-UP"];

/** 3.6.0.15 O2-8: the block is closed until asked for (the owner's rule: a section he uses rarely is closed by default,
 *  opened by its button, and has a close button). Its one row's button: "Change" while closed, "Close" while open. */
export function toggleParts(open: boolean): { word: string; expanded: boolean } {
  return { word: open ? "Close" : "Change", expanded: open };
}

/** The agent the MODEL block reads for the sheet of target `id`: a member's own helper, main's "main", else none. */
export function modelAid(id: string): string | null {
  if (id.startsWith("member:")) return id.slice("member:".length) || null;
  return id === "box:main" ? "main" : null;
}

/** 3.6.0.15 O2-9: the block belongs to the card's CHOSEN agent, as Pause, Stop and the steer box do: on a GROUP's card
 *  (opened from its head, folded or open) the chosen row's agent `pickAid`, none without one; a member's and main's card
 *  as before (`modelAid`); a workflow block's, a step's, a line label's: none. */
export function modelFor(id: string, pickAid: string | null): string | null {
  return id.startsWith("group:") ? pickAid || null : modelAid(id);
}

/** The block's row heading: "MODEL" on a member's and main's card, "MODEL of {name}" on a group's (the chosen row's name). */
export function headingOf(id: string, name: string): string {
  return id.startsWith("group:") ? `MODEL of ${name}` : "MODEL";
}

/** 3.6.0.16 U4 (controls hold still; a text is never cut): on a group's card the MODEL row reserves, from the card's first
 *  draw, the room its LONGEST heading needs: the headings of every member the card has named (`kept`: it never shrinks,
 *  a helper that joins may grow it once), drawn as invisible sizers in the shown heading's grid cell, so choosing a row
 *  moves nothing under the pointer; nothing is measured in script. A member's and main's card: none (unchanged). */
export function headRoom(id: string, kept: string[], names: string[]): string[] {
  if (!id.startsWith("group:")) return [];
  const out = [...kept];
  for (const n of names) if (!out.includes(headingOf(id, n))) out.push(headingOf(id, n));
  return out.length === kept.length ? kept : out;
}

/** 3.6.0.16 U5: the rows keep the height of the first draw of an ANSWER (a read that worked), never of "reading" nor of
 *  the error row ("Could not read ..."): an error row holds nothing, so a read that answers after it holds its own. */
export const holdsRoom = (got: ModelGot | null): boolean => !!got && got !== "reading" && !("error" in got);

/** What a refused pick or Undo reads: the route's own line, else the page's "Not saved: {error}." (a pick) or, for Undo,
 *  the design's Undo refusal head, "Not undone: {error}.". */
export function refusedLine(data: Record<string, unknown> | undefined, error: string, undo = false): string {
  const line = data && typeof data.line === "string" ? data.line : "";
  return line || `${undo ? "Not undone" : "Not saved"}: ${error.replace(/\.$/, "")}.`;
}

/** The opened block's parts, letter for letter; while the GET reads, its one row. MAIN keeps no room for Undo: a pick
 *  for main has none (its answer's `undo` is null). */
export function blockParts(got: ModelGot, after: After | null): BlockParts {
  const parts: BlockParts = { heading: "MODEL", label: "Model", first: "", rows: [], picker: false, edit: "", make: "", undo: "",
    btns: false, undoRoom: false };
  if (got === "reading") return { ...parts, rows: ["Reading this helper's agent..."] };
  if ("error" in got) return { ...parts, rows: [`Could not read this helper's agent: ${got.error}`] };
  const undoRoom = !!got.can && got.kind !== "MAIN";
  const edit = got.kind === "MINE" ? "Edit in Agents" : "";
  const make = MADE.includes(got.kind) ? "Make it an agent" : "";
  return {
    ...parts,
    first: got.first || "",
    rows: (after ? after.line : got.line).split("\n").filter((r) => r !== ""),
    picker: !!got.can,
    edit,
    make,
    undo: after && after.undo ? "Undo" : "",
    btns: undoRoom || !!edit || !!make,
    undoRoom,
  };
}
