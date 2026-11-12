// Live's one sentence (3.3.18.0 "The living canvas", the owner: "this harness should give users the best real-time
// visualization and clarity of what is going on with multi-model multi-workflow jobs"): what is going on right now,
// composed from facts the page already has (no model call, no request) by a small fixed grammar:
//
//   [what waits on you]; [N agents <doing> in <block>, ...]; [waiting on: <agent> -> <what>] · on N models · $spend
//
// Waits on you comes FIRST. <doing> is the PHRASES table read from each agent's wait (its tool, a model reply, writing).
// The buckets are per block (the plan under it) or per group (a task, a square), the biggest first, and the sentence is
// cut to MAX_CHARS by folding the last buckets into "and N more". The running seconds of a wait and the elapsed time are
// NOT in the sentence (they tick; the bar draws them beside it), so it changes only when a fact does. Pure.
import { shortModel } from "../../../lib/modelName";
import { short } from "../../orchestra/format";
import type { LiveNode } from "../../roles/liveModel";
import { liveSpend } from "./spend";
import type { Wait, WaitPath } from "./waits";

export const MAX_CHARS = 140;

/** What an agent is doing, in words, by its wait (a tool by its name). */
export const PHRASES: Record<string, string> = {
  Read: "reading", Grep: "searching", Glob: "searching", LS: "reading", NotebookRead: "reading", Edit: "editing", MultiEdit: "editing",
  Write: "writing files", NotebookEdit: "editing", Bash: "running commands", WebFetch: "on the web", WebSearch: "on the web",
  copilot_ask: "asking Copilot", Agent: "delegating", Task: "delegating", Workflow: "delegating", "~model": "thinking", "~writing": "writing",
  "~queued": "queued", "~tool": "using tools",
};

export function doing(w: Wait | undefined): string {
  if (!w) return "";
  if (w.kind === "model") return PHRASES["~model"];
  if (w.kind === "agent") return PHRASES.Agent;
  if (w.kind === "nothing") return w.what.startsWith("queued") ? PHRASES["~queued"] : PHRASES["~writing"];
  if (w.kind === "tool") return PHRASES[w.what.split(/\s/)[0]] || PHRASES["~tool"];
  return "";
}

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

export type Narration = { text: string; head: string; waitText: string; tail: string; rows: [string, string][] };

/** The sentence for the drawn agents. `where`: an agent's block or group title ("" for none). */
export function narrate(nodes: LiveNode[], waits: Map<string, Wait>, path: WaitPath, where: (n: LiveNode) => string): Narration {
  const agents = nodes.filter((n) => waits.has(n.id));
  if (!agents.length) return { text: "", head: "", waitText: "", tail: "", rows: [] };
  const asks = agents.filter((n) => waits.get(n.id)!.kind === "you");
  const ask = asks.length ? `waiting on you: ${short(waits.get(asks[0].id)!.what, 48)}${asks.length > 1 ? ` (and ${asks.length - 1} more)` : ""}` : "";
  const buckets = new Map<string, number>();
  const rows = new Map<string, LiveNode[]>();
  for (const n of agents) {
    const w = waits.get(n.id)!;
    const at = where(n);
    rows.set(at || "the session", [...(rows.get(at || "the session") || []), n]);
    if (w.kind === "you") continue;
    const k = `${doing(w)}|${at}`;
    buckets.set(k, (buckets.get(k) || 0) + 1);
  }
  const parts = [...buckets].sort((a, b) => b[1] - a[1]).map(([k, c]) => { const [what, at] = k.split("|"); return `${plural(c, "agent")} ${what}${at ? ` in ${short(at, 24)}` : ""}`; });
  const lw = !ask && path.leaf && path.wait && (path.wait.kind === "tool" || path.wait.kind === "model") ? `waiting on: ${path.leaf.role && path.leaf.role !== path.leaf.name ? path.leaf.role : path.leaf.name} -> ${short(path.wait.what, 36)}` : "";
  const models = new Set(agents.map((n) => shortModel(n.model)).filter(Boolean)).size;
  const spend = liveSpend(nodes); // 3.4.1.0 R5 (defect 33): the agents, not their session and machine nodes again
  const tail = `${models ? ` · on ${plural(models, "model")}` : ""} · $${spend >= 1 ? spend.toFixed(2) : spend.toFixed(3)}`;
  const build = (ps: string[], more: number) => [ask, [...ps, more ? `and ${more} more` : ""].filter(Boolean).join(", "), lw].filter(Boolean).join("; ");
  let keep = parts.length, head = build(parts, 0);
  while (keep > 1 && (head + tail).length > MAX_CHARS) (keep -= 1), (head = build(parts.slice(0, keep), parts.length - keep));
  const waitText = lw ? lw : "";
  const text = head + tail;
  const table: [string, string][] = [...rows].map(([at, ms]) => {
    const n = (f: (w: Wait) => boolean) => ms.filter((m) => f(waits.get(m.id)!)).length;
    const live = n((w) => w.kind !== "you"), you = n((w) => w.kind === "you");
    const ml = [...new Set(ms.map((m) => shortModel(m.model)).filter(Boolean))].join(", ");
    const cost = liveSpend(ms);
    return [at, [live && `${live} working`, you && `${you} waiting on you`, ml, `$${cost.toFixed(3)}`].filter(Boolean).join(" · ")];
  });
  return { text, head, waitText, tail, rows: table.slice(0, 8) };
}
