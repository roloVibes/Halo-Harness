// 3.3.16.0 R1b, "the inspector says one thing at a time": the lineup's blocks (what the summary lists and what one
// page edits), each block's one-line state in mono when it is set, and the summary's plain-words lines. What Halo does
// when a block is not set is field_help.py's LINEUP_DEFAULTS (GET /api/field-help `lineup_defaults`), the same words
// the TUI's lineup view prints; this file only shortens it to its first clause for the summary's row.
import { shortRef } from "../shared/catalog";
import { SECTIONS } from "./sections";
import { keyOf, priceText } from "./store";
import type { Graph, ModelRow, Raw } from "./types";

type Rec = Record<string, unknown>;
const rec = (v: unknown): Rec => (v && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : {});
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const plural = (n: number, one: string, many = one + "s") => `${n} ${n === 1 ? one : many}`;

/** A block of the lineup: the header, the opt-ins, the local schedule, then the nine sections (sections.ts). */
export type LineupBlock = { id: string; title: string; section: boolean; defaultKey?: string };

export const HEAD_BLOCKS: LineupBlock[] = [
  { id: "description", title: "Description and how it works", section: false },
  { id: "workers", title: "Where workers run", section: false, defaultKey: "isolation" },
  { id: "schedule", title: "Schedule and warm set", section: false },
];
export const LINEUP_BLOCKS: LineupBlock[] = [...HEAD_BLOCKS, ...SECTIONS.map((d) => ({ id: d.name, title: d.title, section: true, defaultKey: d.name }))];
export const lineupBlock = (id: string) => LINEUP_BLOCKS.find((b) => b.id === id);

/** The card's pages (Assignment): its slot and its own model; the bio opens in the Bios panel. */
export const CARD_PAGES = [
  { id: "slot", title: "Slot: role, alias, instances, routing words" },
  { id: "model", title: "Model override" },
];

const isSet = (v: unknown) => v !== undefined && v !== null && !(typeof v === "object" && !Array.isArray(v) && !Object.keys(v as Rec).length);

/** Whether the lineup sets the block (the header block: a description or an about). */
export function blockSet(id: string, raw: Raw | null): boolean {
  if (!raw) return false;
  if (id === "description") return !!(raw.description || raw.about || raw.extends);
  if (id === "workers") return isSet(raw.isolation) || isSet(raw.secrets) || isSet(rec(raw.tools).capabilities);
  if (id === "schedule") return false;
  return isSet(raw[id]);
}

/** The first clause of a default line: what the summary's row shows (the page shows it all). */
export const firstClause = (line: string) => (line.split(/[;:]/)[0] || line).trim();

function money(v: unknown): string {
  const n = Number(v);
  return Number.isFinite(n) ? "$" + (n % 1 ? n.toFixed(2) : String(n)) : String(v);
}

function joined(parts: (string | false | undefined | null)[]): string {
  return parts.filter(Boolean).join(", ");
}

/** The block's state in mono when it is set ("mode by-skill, 3 at once"). */
export function stateLine(id: string, raw: Raw | null): string {
  const r = raw || {};
  const b = rec(r[id]);
  switch (id) {
    case "description":
      return String(r.description || (r.about ? "about written" : "") || (r.extends ? `extends ${r.extends}` : ""));
    case "workers": {
      const iso = typeof r.isolation === "string" ? r.isolation : isSet(r.isolation) ? String(rec(r.isolation).mode || "container") : "";
      const caps = list(rec(r.tools).capabilities);
      return joined([iso && `isolation ${iso}`, isSet(r.secrets) && `secrets ${rec(r.secrets).broker || "set"}`, caps.length > 0 && plural(caps.length, "capability", "capabilities")]);
    }
    case "delegation":
      return joined([!!b.mode && `mode ${b.mode}`, b.max_parallel != null && `${b.max_parallel} at once`, b.max_depth != null && `depth ${b.max_depth}`,
                     !!b.handoff && `hand-back ${b.handoff}`, !!b.forward_text && "forwards text"]);
    case "routing": {
      const pairs = Object.entries(b).map(([k, v]) => `${k} -> ${v}`);
      return pairs.slice(0, 2).join(", ") + (pairs.length > 2 ? ` +${pairs.length - 2}` : "");
    }
    case "budget":
      return joined([b.max_budget_usd != null && `${money(b.max_budget_usd)} cap`, b.max_total_turns != null && `${b.max_total_turns} turns`,
                     !!b.max_wall_time && String(b.max_wall_time), !!b.band && `band ${b.band}`, !!b.agents_may_exceed && "members may exceed"]);
    case "escalation": {
      const on = list(b.triggers).join(", ");
      return joined([on ? `on ${on}` : "no trigger", b.to ? `-> ${shortRef(String(b.to))}` : "no target", !!b.ask && "asks first"]);
    }
    case "context": {
      const mem = rec(b.memory);
      return joined([list(b.files).length > 0 && plural(list(b.files).length, "file"), list(b.skills).length > 0 && plural(list(b.skills).length, "skill"),
                     !!mem.namespace && `memory ${mem.namespace}`]);
    }
    case "permissions": {
      const rules = rec(b.rules);
      return joined([!!b.mode && `mode ${b.mode}`, ...(["deny", "ask", "allow"] as const).map((k) => list(rules[k]).length > 0 && `${list(rules[k]).length} ${k}`),
                     !!b.offline && "offline"]);
    }
    case "pipeline": {
      const stages = list(b.stages).map((s) => String(rec(s).name || "?"));
      return stages.length ? `${plural(stages.length, "stage")}: ${stages.join(" -> ")}` : "";
    }
    case "acceptance":
      return joined([!!b.prompt && "smoke prompt", !!b.expect && `expects ${JSON.stringify(String(b.expect))}`, !!b.test && `test: ${b.test}`, b.review === true && "plan reviewed first"]);
    case "tiers": {
      const tiers = list(r.tiers).map((t) => String(rec(t).name || "?"));
      return tiers.length ? `${plural(tiers.length, "tier")}: ${tiers.join(", ")}` : "";
    }
    default:
      return "";
  }
}

/** "4 cards in 2 tiers: lead, coder x2, reviewer". */
export function whoLine(graph: Graph | null): string {
  const nodes = graph?.nodes || [];
  if (!nodes.length) return "no cards yet";
  const names = nodes.map((n) => keyOf(n) + (n.instances > 1 ? ` x${n.instances}` : ""));
  const tiers = (graph?.tiers || []).filter((t) => !t.implicit).length;
  return `${plural(nodes.length, "card")}${tiers ? ` in ${plural(tiers, "tier")}` : ""}: ${names.join(", ")}`;
}

/** The main card's model, its price and the band an auto member's pick uses. */
export function mainLine(graph: Graph | null, row: ModelRow | undefined, raw: Raw | null): string {
  const main = graph?.nodes.find((n) => n.role === "main");
  if (!main) return "no main card: a session on it starts on your default model";
  const band = String(rec(raw?.budget).band || "mid");
  return `${main.model ? shortRef(main.model) : "no model resolves"} · ${priceText(row)} per 1M · band ${band}`;
}

/** Where the workers run, from `isolation`. */
export function workersLine(raw: Raw | null): string {
  const iso = typeof raw?.isolation === "string" ? raw.isolation : isSet(raw?.isolation) ? String(rec(raw?.isolation).mode || "container") : "";
  if (iso === "container") return "an Orchestra lane runs in a per-run container, in its own worktree";
  if (iso === "user") return "an Orchestra lane runs as a scoped OS user, in its own worktree";
  return "here, as you; an Orchestra run gives each lane its own worktree";
}

/** "budget $12 cap, 40 turns" or "no cap: Halo stops at the bio budgets". */
export function spendLine(raw: Raw | null): string {
  const b = rec(raw?.budget);
  const caps = joined([b.max_budget_usd != null && `${money(b.max_budget_usd)} cap`, b.max_total_turns != null && `${b.max_total_turns} turns`, !!b.max_wall_time && String(b.max_wall_time)]);
  return caps ? `budget ${caps}` : "no cap: Halo stops at the bio budgets";
}

/** "9 sections: 3 set, 6 at Halo's default". */
export function policyLine(raw: Raw | null): string {
  const set = SECTIONS.filter((d) => blockSet(d.name, raw)).length;
  return `${SECTIONS.length} sections: ${set} set, ${SECTIONS.length - set} at Halo's default`;
}
