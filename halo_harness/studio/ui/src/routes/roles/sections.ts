// The structured editors of a lineup's top sections (3.0.7.0 R2): one form
// per section, its fields named by their path inside the section, the same
// keys and choices teams_yaml.validate_team_template checks. A field is a
// text, a number, a yes/no, a choice, a list (comma separated), a set of
// checks, a mapping (routing: task kind -> role or alias) or rows of small
// records (org positions, pipeline stages, tiers). Every section also has a
// YAML toggle that edits its raw body.

export type Col = { key: string; label: string; kind: "text" | "number" | "select" | "target" | "list" | "members"; options?: string[]; width?: number };

export type FieldDef =
  | { path: string; label: string; kind: "text" | "number" | "bool" | "list" | "model"; hint?: string; placeholder?: string }
  | { path: string; label: string; kind: "select"; options: string[]; hint?: string }
  | { path: string; label: string; kind: "checks"; options: string[]; hint?: string }
  | { path: string; label: string; kind: "map"; hint?: string; keyLabel: string }
  | { path: string; label: string; kind: "rows"; cols: Col[]; hint?: string; add: Record<string, unknown> };

export type SectionDef = { name: string; title: string; about: string; list?: boolean; fields: FieldDef[] };

export const SECTIONS: SectionDef[] = [
  { name: "delegation", title: "Delegation", about: "How the main agent hands work to the others.", fields: [
    { path: "mode", label: "Mode", kind: "select", options: ["", "manual", "by-skill", "round-robin"], hint: "by-skill routes by the words in a task" },
    { path: "max_parallel", label: "At most at once", kind: "number" },
    { path: "max_depth", label: "Max depth", kind: "number", hint: "1: only main spawns; a three-tier stack needs 2" },
    { path: "handoff", label: "Hand-back shape", kind: "select", options: ["", "summary", "full", "structured"] },
    { path: "forward_text", label: "Forward the member's text as it writes", kind: "bool" },
  ] },
  { name: "routing", title: "Routing", about: "Which role or alias a kind of task goes to.", fields: [
    { path: "", label: "Task kind -> member", kind: "map", keyLabel: "task kind", hint: "default catches the rest" },
  ] },
  { name: "budget", title: "Budget", about: "When delegation stops: money, turns, time.", fields: [
    { path: "max_budget_usd", label: "Max spend (USD)", kind: "number" },
    { path: "max_total_turns", label: "Max turns, all members", kind: "number" },
    { path: "max_wall_time", label: "Max wall time", kind: "text", placeholder: "3h, 45m, 1d" },
    { path: "agents_may_exceed", label: "A member may go past its own bio's budget", kind: "bool" },
  ] },
  { name: "escalation", title: "Escalation", about: "When a member switches to a bigger model.", fields: [
    { path: "triggers", label: "Triggers", kind: "checks", options: ["tool_failures", "context_overflow", "budget_exhausted"] },
    { path: "to", label: "Switch to", kind: "model" },
    { path: "ask", label: "Ask me first (the approval card)", kind: "bool" },
    { path: "allow_fallbacks", label: "Allow the bio's fallbacks first", kind: "bool" },
  ] },
  { name: "context", title: "Context", about: "What every member reads, and the shared memory.", fields: [
    { path: "files", label: "Files every member reads", kind: "list", placeholder: "CLAUDE.md, plans/STATUS.md" },
    { path: "skills", label: "Skills", kind: "list" },
    { path: "memory.namespace", label: "Memory namespace", kind: "text" },
    { path: "memory.writers", label: "Who may write the memory", kind: "list", placeholder: "boss" },
  ] },
  { name: "permissions", title: "Permissions", about: "On top of each member bio's own rules.", fields: [
    { path: "mode", label: "Mode", kind: "select", options: ["", "default", "auto", "acceptEdits", "plan", "bypassPermissions"] },
    { path: "rules.deny", label: "Deny", kind: "list", placeholder: "Bash(git push*)" },
    { path: "rules.ask", label: "Ask", kind: "list" },
    { path: "rules.allow", label: "Allow", kind: "list" },
    { path: "offline", label: "Offline (no network tools)", kind: "bool" },
  ] },
  { name: "org", title: "Org", about: "Who reports to whom (a card dropped onto a card writes this).", fields: [
    { path: "positions", label: "Positions", kind: "rows", add: { title: "" }, cols: [
      { key: "title", label: "title", kind: "target" }, { key: "agent", label: "bio", kind: "text" }, { key: "reports_to", label: "reports to", kind: "target" }] },
  ] },
  { name: "pipeline", title: "Pipeline", about: "Stages that run in order; a required gate must pass.", fields: [
    { path: "stages", label: "Stages", kind: "rows", add: { name: "", role: "main", gate: "required" }, cols: [
      { key: "name", label: "stage", kind: "text" }, { key: "role", label: "role or alias", kind: "target" },
      { key: "gate", label: "gate", kind: "select", options: ["required", "optional"] }] },
  ] },
  { name: "acceptance", title: "Acceptance", about: "The check halo doctor --teams runs on this lineup.", fields: [
    { path: "prompt", label: "Prompt", kind: "text" },
    { path: "expect", label: "Expect (a substring, or non-empty)", kind: "text" },
  ] },
  { name: "tiers", title: "Tiers", list: true, about: "Stacks of members: each spawns only into the next tier down.", fields: [
    { path: "", label: "Tiers, top first", kind: "rows", add: { name: "", members: [] }, hint: "tier 0 holds main alone; members left out join the last tier", cols: [
      { key: "name", label: "tier", kind: "text" }, { key: "members", label: "members", kind: "members" }, { key: "max_parallel", label: "max at once", kind: "number", width: 70 }] },
  ] },
];

export const sectionDef = (name: string) => SECTIONS.find((s) => s.name === name);

// -- paths inside a section --------------------------------------------------------------
type Obj = Record<string, unknown>;

export function getPath(obj: unknown, path: string): unknown {
  if (!path) return obj;
  let cur: unknown = obj;
  for (const k of path.split(".")) cur = cur && typeof cur === "object" ? (cur as Obj)[k] : undefined;
  return cur;
}

const empty = (v: unknown) => v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length) || (typeof v === "object" && !Array.isArray(v) && !Object.keys(v as Obj).length);

/** Set `path` in `obj` to v (an empty v removes it, and any mapping it leaves empty). */
export function setPath(obj: Obj, path: string, v: unknown): void {
  const keys = path.split(".");
  const chain: Obj[] = [obj];
  for (const k of keys.slice(0, -1)) {
    const cur = chain[chain.length - 1];
    if (!cur[k] || typeof cur[k] !== "object" || Array.isArray(cur[k])) cur[k] = {};
    chain.push(cur[k] as Obj);
  }
  const last = keys[keys.length - 1];
  if (empty(v)) delete chain[chain.length - 1][last];
  else chain[chain.length - 1][last] = v;
  for (let i = chain.length - 1; i > 0; i--) if (empty(chain[i])) delete chain[i - 1][keys[i - 1]];
}

export const splitList = (text: string) => text.split(",").map((s) => s.trim()).filter(Boolean);
