// What the drawn work spent (3.4.1.0 R5, live re-check defect 33): the agents' own costs. On the fleet scope a machine,
// a session or a mission part is a node too, and it carries the money its agents spent (a session's spend IS its
// agents'), so summing every node said $0.015 for a member's one `halo -p` session of $0.0075. No imports: tests run it.
// 3.4.1.1: `spendText` never prints a spend that is not zero as $0.000 (defect 44: $0.0004 read "$0.000"); `spendWords`
// says "cost unknown at this moment" for a replay whose record cannot give the figure then (defect 60), never $0.
export type Costed = { kind?: string; cost: number | null; costUnknown?: boolean };

export function liveSpend(nodes: Costed[]): number {
  return nodes.reduce((s, n) => s + (n.kind ? 0 : Number(n.cost) || 0), 0);
}

/** "$1.23", "$0.012", "$0.0004", "<$0.0001"; "$0.000" only for nothing spent. */
export function spendText(usd: number): string {
  if (usd >= 1) return `$${usd.toFixed(2)}`;
  if (usd >= 0.01 || usd <= 0) return `$${Math.max(0, usd).toFixed(3)}`;
  return usd < 0.00005 ? "<$0.0001" : `$${usd.toFixed(4)}`;
}

/** The agents' spend in words, or "cost unknown at this moment" when one of them has no figure at this moment. */
export function spendWords(nodes: Costed[]): string {
  return nodes.some((n) => !n.kind && n.costUnknown) ? "cost unknown at this moment" : spendText(liveSpend(nodes));
}

/** GET fleet/costs (studio/live_panels_api.py): live/caps.spend -- each harness's today from its records, finished
 *  sessions too, by project and for the fleet -- and the caps. 3.4.1.1 (65): the glance's one source for its spend. */
export type CostsView = {
  caps: Record<string, number | null>; reached: { scope: string; key: string; label: string }[];
  fleet?: number; complete?: boolean; harnesses?: { id: string; local?: boolean; usd: number; unknown?: string[] }[];
  projects?: { key: string; usd: number }[];
};
type Row = { session_id: string; cwd?: string | null; project?: { repo?: string | null; root?: string | null } | null };
export type Spend = { spent: string; cap: string; pct: number | null; reached: boolean };

/** A session row's project key, as live/caps.project_key names it. */
export const projectOf = (s: Row) =>
  String(s.project?.repo || s.project?.root || s.cwd || "").replace(/\\/g, "/").replace(/\/+$/, "").split("/").pop() || "no project";

/** Today's spend against the first cap set of this machine's, the watched session's project's, the fleet's -- the same
 *  figures the caps count (GET fleet/costs); "$x+" when a model had no price, never $0 for what Halo cannot price; no
 *  cap: this machine's today and "no cap set". */
export function spendOf(harnesses: { local?: boolean; sessions?: Row[] }[], costs: CostsView | null, sid: string): Spend {
  if (!costs || !Array.isArray(costs.harnesses)) return { spent: "not read yet", cap: "the caps are not read yet", pct: null, reached: false };
  const watched = (harnesses.find((h) => h.local)?.sessions || []).find((s) => s.session_id === sid);
  const project = watched ? projectOf(watched) : "";
  const mine = costs.harnesses.find((h) => h.local);
  const c = costs.caps || {};
  const whole = costs.complete !== false;
  const scopes: [string, string, number | null | undefined, number | undefined, boolean][] = [
    ["harness", "this machine's cap", c.per_harness_usd_per_day, mine?.usd, !mine?.unknown?.length],
    ["project", `the cap on ${project}`, project ? c.per_project_usd_per_day : null, (costs.projects || []).find((p) => p.key === project)?.usd ?? 0, whole],
  ];
  const first = scopes.find((x) => !!x[2]);
  const [, label, cap, usd, known] = first || scopes[0];
  const spent = typeof usd === "number" ? `${spendText(usd)}${known ? "" : "+"}` : "unknown";
  if (!first) return { spent, cap: "no cap set", pct: null, reached: false };
  const reached = (costs.reached || []).some((r) => r.scope === first[0]);
  return { spent, cap: `of ${spendText(Number(cap))} a day, ${label}`, pct: typeof usd === "number" ? Math.min(1, usd / Number(cap)) : null, reached };
}
