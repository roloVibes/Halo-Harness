// The post-run coach's result (3.0.9.0 R3; halo_harness/orchestra/coach.py),
// the same for every run kind: GET orchestra/<run>/coach, flow/runs/<id>/coach,
// fleet/missions/<id>/coach and team/coach?run=. 3.1.3.0 R1: each card's lead
// paragraph and applied state, and the POST <route>/ask | apply | undo shapes.

export type CoachRunKind = "orchestra" | "flow" | "mission" | "team";
export type CoachKind = "prompt" | "model" | "tools" | "structure" | "coordination";
export type CoachSeverity = "high" | "medium" | "low";

/** What Apply writes: a bio field (`models.preference`, `tools.allow`, `context.prompt_notes`), a lineup
 *  role (`roles.<role>`) or a plan job's field (`job-2.after`, `job-3.drop`), after one confirm. */
export type CoachApply = { target: "bio" | "lineup" | "plan"; name: string; field: string; value: unknown };

export type Suggestion = {
  id: string;
  kind: CoachKind;
  severity: CoachSeverity;
  lane_or_part: string | number | null;
  bio: string;
  text: string;
  why: string[];
  apply: CoachApply | null;
  /** The run's lead's paragraph (Ask the model), null until asked. */
  paragraph?: string | null;
  paragraph_error?: string;
  /** Applied / Undone, from ~/.halo/coach/applied.jsonl. */
  applied?: CoachApplied | null;
};

export type CoachApplied = { state: "applied" | "undone"; apply_id: string; file: string; ts: number };

/** POST <route>/apply {id}: the confirm card (nothing written yet). */
export type CoachPreview = {
  id: string; target: string; name: string; field: string; value: unknown;
  file: string; exists: boolean; before: string; after: string; diff: string[];
};

export type CoachAsk = { id: string; paragraph: string; error: string; model?: string; role?: string; cached: boolean };

export type CoachResult = {
  run: string;
  kind: CoachRunKind;
  suggestions: Suggestion[];
  evidence: Record<string, unknown>;
  model: boolean;
  computed?: number;
  cached?: boolean;
};

export const KIND_ORDER: CoachKind[] = ["tools", "model", "prompt", "structure", "coordination"];
export const KIND_LABEL: Record<CoachKind, string> = {
  prompt: "PROMPT",
  model: "MODEL",
  tools: "TOOLS",
  structure: "STRUCTURE",
  coordination: "COORDINATION",
};
