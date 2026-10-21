// A session's own figures from the frames the terminal's status bar moves on
// (3.1.8.0 R6 "Studio keeps up with the terminal"; tui/dispatch.py hands
// them to tui/widgets/statusbar.py `apply_status`): `message_end` at the end
// of every model call (the running cost, the token totals, the context fill;
// its `turn` is the user turn it belongs to) and `status` at a turn's start
// and end (the phase, the model, the turn, the cost). Only the session's own
// frames count: one with an `agent_id`, or whose `data.session_id` starts
// with `agent-`, is a sub-agent's (the TUI's rule). A field the frame leaves
// None stays as it was (the status bar's rule). sync.ts applies them through
// `mapSession`; fresh.ts keeps them when an older GET fleet answer lands.
import type { FeedFrame } from "../../lib/events";
import type { AgentRow, SessionRow } from "./types";

export const FIGURE_KINDS = ["message_end", "status"];

export const num = (v: unknown): number | null => (typeof v === "number" && isFinite(v) ? v : null);

/** The session's own frame (never a sub-agent's: the TUI's rule, dispatch.py / runtime.py). */
export function ownFrame(f: FeedFrame): boolean {
  const d = (f.data || {}) as Record<string, unknown>;
  return !f.agent_id && !String(d.session_id || "").startsWith("agent-");
}

export type Figures = Partial<Pick<SessionRow, "cost_usd" | "tokens_in" | "tokens_out" | "context_tokens" | "context_limit" | "turns" | "model" | "busy">>;

/** What the frame says about the session: only the numbers it carries; `status` adds the model and the phase as busy. */
export function figuresOf(f: FeedFrame): Figures {
  const d = (f.data || {}) as Record<string, unknown>;
  const out: Figures = {};
  const put = (k: "cost_usd" | "tokens_in" | "tokens_out" | "context_tokens" | "context_limit", v: unknown) => {
    const n = num(v);
    if (n != null) out[k] = n;
  };
  put("cost_usd", d.cost_usd);
  put("tokens_in", d.total_input_tokens);
  put("tokens_out", d.total_output_tokens);
  put("context_tokens", d.context_tokens);
  put("context_limit", d.context_limit);
  const turn = num(f.event === "status" ? d.turn : f.turn);
  if (turn != null && turn > 0) out.turns = turn;
  if (f.event === "status") {
    if (typeof d.model === "string" && d.model) out.model = d.model;
    if (d.phase === "thinking") out.busy = true;
    else if (d.phase === "idle") out.busy = false;
  }
  return out;
}

/** The row with the frame's figures on it; its status follows the phase (an open ask keeps it waiting). */
export function withFigures(ss: SessionRow, fig: Figures): SessionRow {
  const next: SessionRow = { ...ss, ...fig };
  if (typeof fig.busy === "boolean" && ss.status !== "waiting") next.status = fig.busy ? "busy" : "idle";
  return next;
}

const higher = (a: unknown, b: unknown): number | null => {
  const x = num(a), y = num(b);
  return x == null ? y : y == null ? x : Math.max(x, y);
};

/** An agent row with a newer one over it; its tokens are the higher of the two (a frame and a GET may arrive in either order). */
export function agentWith(old: AgentRow, row: AgentRow): AgentRow {
  return { ...old, ...row, tokens_in: higher(old.tokens_in, row.tokens_in), tokens_out: higher(old.tokens_out, row.tokens_out) };
}

/** A GET's session row with the figures a newer frame left on `had`: the higher spend, tokens and turns, the frame's context. */
export function keepFigures(got: SessionRow, had: SessionRow, phase: boolean | null): SessionRow {
  const out: SessionRow = { ...got };
  for (const k of ["cost_usd", "tokens_in", "tokens_out", "turns"] as const) out[k] = higher(had[k], got[k]);
  for (const k of ["context_tokens", "context_limit"] as const) if (num(had[k]) != null) out[k] = had[k];
  if (phase != null && got.status !== "waiting") {
    out.busy = phase;
    out.status = phase ? "busy" : "idle";
  }
  return out;
}
