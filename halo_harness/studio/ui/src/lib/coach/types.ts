// The post-run coach's result (3.0.9.0 R3; halo_harness/orchestra/coach.py),
// the same for every run kind: GET orchestra/<run>/coach,
// fleet/missions/<id>/coach and team/coach?run=. 3.1.3.0 R1: each card's lead
// paragraph and applied state, and the POST <route>/ask | apply | undo shapes.
// 3.1.6.0 R2: the probe (orchestra/coach_probe.py): its card (kind "probe",
// the contrast table, Apply = the composed overlay), its status and its cost line.

export type CoachRunKind = "orchestra" | "mission" | "team";
export type CoachKind = "probe" | "prompt" | "model" | "tools" | "structure" | "coordination";
export type CoachSeverity = "high" | "medium" | "low";

/** One change a probe card's Apply writes (a bio field, a lineup role or entry, a plan job's after). */
export type CoachChange = { target: "bio" | "lineup" | "plan"; name: string; field: string; value: unknown };

/** What Apply writes: a bio field (`models.preference`, `tools.allow`, `context.prompt_notes`), a lineup
 *  role (`roles.<role>`) or a plan job's field (`job-2.after`, `job-3.drop`), after one confirm; a probe
 *  card's `overlay`: several changes, maybe in several files. */
export type CoachApply = {
  target: "bio" | "lineup" | "plan" | "overlay";
  name: string;
  field: string;
  value: unknown;
  changes?: CoachChange[];
};

/** One row of a probe card's contrast table: the run itself first, then each candidate. */
export type ProbeRow = {
  id: string;
  kind: string;
  status?: string;
  stop_reason?: string;
  tests_ok?: boolean | null;
  passed?: number | null;
  tests_delta?: number;
  cost_usd?: number | null;
  cost_x?: number | null;
  steps?: number | null;
  steps_delta?: number;
  rank?: number | null;
  wins?: string[];
  picked?: boolean;
  error?: string;
};

export type Suggestion = {
  id: string;
  kind: CoachKind;
  severity: CoachSeverity;
  lane_or_part: string | number | null;
  bio: string;
  text: string;
  why: string[];
  apply: CoachApply | null;
  /** The run's lead's paragraph (Ask the model), null until asked; a probe card: the judge's why. */
  paragraph?: string | null;
  paragraph_error?: string;
  /** Applied / Undone, from ~/.halo/coach/applied.jsonl. */
  applied?: CoachApplied | null;
  /** A probe card's contrast table and totals. */
  table?: ProbeRow[];
  probe?: { runs: number; k: number; pick: string; cost_usd: number | null; cap_usd: number | null; ended: number | null };
};

export type CoachApplied = { state: "applied" | "undone"; apply_id: string; file: string; ts: number };

/** POST <route>/apply {id}: the confirm card (nothing written yet); a probe card lists every file. */
export type CoachPreview = {
  id: string; target: string; name: string; field: string; value: unknown;
  file: string; exists: boolean; before: string; after: string; diff: string[];
  files?: string[]; skipped?: string[];
};

export type CoachAsk = { id: string; paragraph: string; error: string; model?: string; role?: string; cached: boolean };

/** The probe's status on the coach result (probe.json), `live` when it runs in this Studio. */
export type ProbeStatus = {
  state?: "running" | "done" | "failed";
  step?: string;
  line?: string;
  runs?: number;
  cap_usd?: number;
  estimate?: string;
  card?: string;
  pick?: string;
  error?: string;
  cost_usd?: number | null;
  live?: boolean;
};

/** POST orchestra/<run>/coach/probe without confirm: what the probe may spend, before it starts. */
export type ProbeEstimate = { k: number; factor: number; runs: number; ref_usd: number; cap_usd: number; total_usd: number; line: string };

export type CoachResult = {
  run: string;
  kind: CoachRunKind;
  suggestions: Suggestion[];
  evidence: Record<string, unknown>;
  model: boolean;
  computed?: number;
  cached?: boolean;
  probe?: ProbeStatus | null;
};

export const KIND_ORDER: CoachKind[] = ["probe", "tools", "model", "prompt", "structure", "coordination"];
export const KIND_LABEL: Record<CoachKind, string> = {
  probe: "PROBE",
  prompt: "PROMPT",
  model: "MODEL",
  tools: "TOOLS",
  structure: "STRUCTURE",
  coordination: "COORDINATION",
};
