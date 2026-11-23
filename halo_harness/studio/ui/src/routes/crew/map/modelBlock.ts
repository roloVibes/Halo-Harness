// The MODEL block's pure rules (3.6.0.15 O2-5, "the box acts"): what the sheet's MODEL block draws for the GET
// crew/agent-model's answer (studio/crew_model_api.py: {kind, name, model, first, line, can, now}) and for what a pick
// or Undo answered. No React, no DOM, no store: node runs it (tests/test_sheet_place.py), as sheetPlace.ts beside
// useSheet.ts; StepInModel.tsx draws it. The block is the sheet's OWN box's (the coordinator's ruling F): a member's
// sheet (that helper) and main's sheet (MAIN) only; a group's sheet has none and asks nothing.

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

/** The sheet opens when Last said's read and the model's read may both open it (each `saidOpen`: answered, or 1 s). */
export function sheetReady(said: boolean, model: boolean): boolean {
  return said && model;
}

/** The agent the MODEL block reads for the sheet of target `id`: a member's own helper, main's "main", else none. */
export function modelAid(id: string): string | null {
  if (id.startsWith("member:")) return id.slice("member:".length) || null;
  return id === "box:main" ? "main" : null;
}

/** What a refused pick or Undo reads: the route's own line, else the page's "Not saved: {error}." (a pick) or, for Undo,
 *  the design's Undo refusal head, "Not undone: {error}.". */
export function refusedLine(data: Record<string, unknown> | undefined, error: string, undo = false): string {
  const line = data && typeof data.line === "string" ? data.line : "";
  return line || `${undo ? "Not undone" : "Not saved"}: ${error.replace(/\.$/, "")}.`;
}

/** The block's parts, letter for letter; null while the GET is still reading (nothing is drawn yet). */
export function blockParts(got: ModelGot, after: After | null): BlockParts | null {
  if (got === "reading") return null;
  const parts: BlockParts = { heading: "MODEL", label: "Model", first: "", rows: [], picker: false, edit: "", make: "", undo: "",
    btns: false, undoRoom: false };
  if ("error" in got) return { ...parts, rows: [`Could not read this helper's agent: ${got.error}`] };
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
    btns: !!got.can || !!edit || !!make,
    undoRoom: !!got.can,
  };
}
