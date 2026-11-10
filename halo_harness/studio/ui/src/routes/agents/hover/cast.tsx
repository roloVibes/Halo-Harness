// A Cast card's hover card (3.3.16.1): the role (or its alias), what its bio is, and the facts the canvas and the stores
// already hold -- the bio, the words that route to it, the model with where it comes from and what it takes, its price
// and window, its tools, its limits (from the lineup entry, and the bio's when that bio is open in the Bios panel), how
// many at once and its tier -- then NOW while an agent of this card runs. A click selects the card: the inspector's
// summary (its Live tab when an agent runs on it).
import { shortRef } from "../../shared/catalog";
import { agentsOf, modelRow, priceText, useRoles } from "../../roles/store";
import { cardActivity, useByNode } from "../../roles/live";
import { sourceText } from "../../roles/tierText";
import type { Raw } from "../../roles/types";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { joined, plural, spent, takesWords } from "./words";

const rec = (v: unknown): Raw => (v && typeof v === "object" && !Array.isArray(v) ? (v as Raw) : {});

/** "$2 cap · 40 turns · 20m", "" when none is set. */
function limitsOf(...srcs: Raw[]): string {
  const l = Object.assign({}, ...srcs.map((s) => rec(s.limits)));
  return joined([l.max_budget_usd != null && `$${l.max_budget_usd} cap`, l.max_iterations != null && `${l.max_iterations} turns`,
                 !!l.timeout && `timeout ${l.timeout}`, l.concurrency != null && `${l.concurrency} at once`]);
}

export function CastHover({ id }: { id: string }) {
  const n = useRoles((s) => s.graph?.nodes.find((x) => x.id === id));
  const row = useRoles((s) => (n ? modelRow(s, n.model) || s.fallback.find((m) => m.ref === n.model) : undefined));
  const bio = useRoles((s) => (n ? s.bios.find((b) => b.name === n.agent) : undefined));
  const open = useRoles((s) => (n && s.bio === n.agent && s.bioData ? s.bioData : null)); // cached only while that bio is open
  const entry = useRoles((s) => (n ? agentsOf(s.raw)[n.index] : undefined));
  const tier = useRoles((s) => s.graph?.tiers.find((t) => t.node_ids.includes(id)));
  const live = useByNode()[id] || [];
  if (!n) return null;
  const from = n.model_source ? sourceText(n.model_source, n.agent) : "";
  const takes = takesWords(row?.takes);
  const price = row && (row.price_in != null || row.price_out != null) ? `${priceText(row)} per 1M` : "";
  const ctx = row?.context || n.context;
  const caps = bio?.capabilities?.length ? bio.capabilities.join(", ") : "";
  const tools = caps ? `capabilities: ${caps}` : n.tools != null ? (n.tools ? plural(n.tools, "tool") : "no tools") : "";
  const limits = limitsOf(rec(entry), rec(open?.resolved));
  const rows: HoverRow[] = [
    ["Bio", joined([n.agent, bio?.kind || n.kind], ", ")],
    ["Used for", n.use_for.length ? n.use_for.join(", ") : "none: the main agent names it"],
    ["Model", n.model ? joined([n.model !== "default" && shortRef(n.model), from && (n.model === "default" ? from : `from ${from}`), takes && `takes ${takes}`])
      : "none resolves"],
    ["Price", joined([price, ctx && `context ${ctx}`])],
    ["Tools", tools],
    ["Limits", limits || (open ? "not set = Halo's defaults" : "")], // the bio's own limits are known only while it is open
    ["Instances", n.instances > 1 ? `up to ${n.instances} at once` : "one at a time"],
    ["Tier", tier ? `${tier.index} (${tier.name})` : ""],
  ];
  const act = cardActivity(live);
  const lead = live.find((a) => a.activity === act) || live[0];
  const usd = live.reduce((t, a) => t + (Number(a.cost_usd) || 0), 0);
  const now = lead && act ? joined([live.length > 1 ? `${live.length} agents` : lead.name, lead.state, lead.current || lead.tool, spent(usd) && `${spent(usd)} so far`]) : "";
  return (
    <HoverBody title={n.alias && n.alias !== n.role ? `${n.alias} (${n.role})` : n.role} is={bio?.description || n.description || ""}
               rows={rows} now={now} foot="Click: its summary in the inspector" />
  );
}
