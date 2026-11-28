// 3.6.0.23 PV (the owner: "a feature that shows the plan of a session ... tracking what's been completed"): a session's
// plan and objective, in words. Pure (tests/test_map_groups.py runs it in node). The plan is main's agent row's `plan`
// (agent/agent_observe.py: his last successful TodoWrite list, capped there; it rides agent_state and the fleet load, so
// a reload keeps it); the objective is main's row's `objective` (the first line of the person's latest prompt of four
// words or more). Nothing here asks a model; nothing is made up: no list, no plan.

export type Todo = { content: string; status: string; activeForm?: string; n?: number };
/** The true counts of main's whole list (the row keeps at most 30 steps: agent_observe.py `plan_count`). */
export type PlanCount = { all: number; done: number };
type Agentish = { agent_id?: string; kind?: string | null; plan?: unknown; plan_count?: unknown; objective?: string | null };
export type Sessionish = { agents?: Agentish[] | null } | null | undefined;

/** Main's row of a session: the one of kind "main", else the one named main. */
export function mainOf(ss: Sessionish): Agentish | undefined {
  const rows = ss?.agents || [];
  return rows.find((a) => a.kind === "main") || rows.find((a) => a.agent_id === "main");
}

const EMPTY: Todo[] = [];
const seen = new WeakMap<object, Todo[]>(); // one array per row's list: a view's selector keeps the same reference

/** Main's plan as the views draw it ([] with none): its items with words, a status of the three TodoWrite knows. */
export function planOf(ss: Sessionish): Todo[] {
  const raw = mainOf(ss)?.plan;
  if (!Array.isArray(raw) || !raw.length) return EMPTY;
  const kept = seen.get(raw);
  if (kept) return kept;
  const list = raw.filter((t): t is Todo => !!t && typeof (t as Todo).content === "string" && !!(t as Todo).content)
    .map((t) => ({ content: t.content, status: STATES.includes(t.status) ? t.status : "pending", activeForm: t.activeForm ? String(t.activeForm) : undefined,
      n: typeof t.n === "number" && t.n > 0 ? t.n : undefined }));
  seen.set(raw, list);
  return list;
}

/** Main's objective ("" before a prompt of four words). */
export const objectiveOf = (ss: Sessionish): string => String(mainOf(ss)?.objective || "");
/** The objective row's held room (FeedPlan.tsx, a hidden twin in the same cell): an objective at its cap (120
 * characters, agent_transcript.first_line) of ordinary letters, so one arriving never moves what is under the row. */
export const OBJECTIVE_ROOM = "collect the three reports and write the summary for the team, then fix the discount order in basket.py and run its suite";

const STATES = ["pending", "in_progress", "completed"];
export const doneOf = (list: Todo[]): number => list.filter((t) => t.status === "completed").length;
export const nowOf = (list: Todo[]): Todo | undefined => list.find((t) => t.status === "in_progress");

/** The Map's top line: "plan: 3 of 7 done" ("" with no plan). */
export const planWords = (list: Todo[] | undefined): string => (list && list.length ? `plan: ${doneOf(list)} of ${list.length} done` : "");

/** Main's true counts: the row's `plan_count`, else the list's own (a row from before the counts). */
export function countOf(ss: Sessionish, list: Todo[] = planOf(ss)): PlanCount {
  const c = mainOf(ss)?.plan_count as Partial<PlanCount> | null | undefined;
  return c && typeof c.all === "number" && typeof c.done === "number" ? { all: c.all, done: c.done } : { all: list.length, done: doneOf(list) };
}
const own = (list: Todo[]): PlanCount => ({ all: list.length, done: doneOf(list) });

export const NO_PLAN = "no plan yet";
/** The Session head's chip: "Plan 3 of 7" (steps done of all), "no plan yet" with none (before his first list, and
 *  after a resume: a resumed session's plan is not rebuilt in this release). */
export const chipWords = (list: Todo[], c: PlanCount = own(list)): string => (list.length ? `Plan ${c.done} of ${c.all}` : NO_PLAN);

/** The chip's hover (hover = summary): the step in progress. */
export function chipHover(list: Todo[], c: PlanCount = own(list)): string {
  if (!list.length) return "No plan yet: when main writes a to-do list, its steps show here";
  const now = nowOf(list);
  if (now) return `Now: ${now.activeForm || now.content}`;
  return c.done === c.all ? "Every step is done" : "No step in progress";
}

/** A step's state as a mark AND a word (a screen reader reads the word; colour is never alone). */
export const STEP: Record<string, { mark: string; word: string }> = {
  pending: { mark: "○", word: "to do" }, in_progress: { mark: "▸", word: "doing" }, completed: { mark: "✓", word: "done" },
};
/** The words a step's line shows (the step in progress: its activeForm) and its twin (the other form): a line holds the
 *  room of both, so a change of state never changes its height. */
export function stepText(t: Todo): { text: string; twin: string } {
  const doing = t.status === "in_progress" && !!t.activeForm;
  return { text: doing ? String(t.activeForm) : t.content, twin: doing ? t.content : t.activeForm || t.content };
}

/** The checklist shows this many steps; more scroll in its own box, the step in progress kept in view. */
export const PLAN_ROWS = 8;

/** A line of the written-out plan: a kept step, or where step numbers are left out (between two kept steps, or after
 *  the last: a list over the row's cap) ONE muted line saying how many. */
export type PlanLine = { step: Todo } | { more: number };
export const moreWords = (n: number): string => `+${n} more steps not shown`;
export function planLines(list: Todo[], all = list.length): PlanLine[] {
  const out: PlanLine[] = [];
  let last = 0;
  for (const t of list) {
    const n = t.n || last + 1;
    if (n > last + 1) out.push({ more: n - last - 1 });
    out.push({ step: t });
    last = n;
  }
  if (list.length && all > last) out.push({ more: all - last });
  return out;
}
