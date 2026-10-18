// The post-run coach's result (3.0.9.0 R3; halo_harness/orchestra/coach.py),
// the same for every run kind: GET orchestra/<run>/coach, flow/runs/<id>/coach,
// fleet/missions/<id>/coach and team/coach?run=.

export type CoachRunKind = "orchestra" | "flow" | "mission" | "team";
export type CoachKind = "prompt" | "model" | "tools" | "structure" | "coordination";
export type CoachSeverity = "high" | "medium" | "low";

/** What Apply fills in: a bio field (`models.preference`, `tools.allow`, `context.prompt_notes`), a lineup
 *  role (`roles.<role>`) or a plan job's field (`job-2.after`, `job-3.drop`). Nothing is saved by the coach. */
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
};

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
