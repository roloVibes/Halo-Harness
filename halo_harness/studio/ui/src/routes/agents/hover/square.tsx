// A workflow square's hover card (3.3.16.1), on the board's card and on a library row: its name, its whole DOES line,
// then its contract -- takes, gives, covers, what it runs on (the lineup's lead and its model, the engine in words), its
// costs and limits, where it comes from and its file -- and its last run with the count, from this halo's sessions'
// receipts (the agent rows that carry `square`). NOW while it is the lit square: who called it, with what need, for how
// long. A click on the board's card opens the inspector's summary; on a library row nothing opens (a row is dragged
// onto the board), the card says so.
import { allAgents, isLive, useFleet, useNow } from "../../fleet/store";
import { squareOf, useWf } from "../workflows/store";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { ago, joined, plural, since, span, spent } from "./words";

const ENGINE: Record<string, string> = { session: "one agent", orchestra: "a run with lanes", mission: "across the fleet (a run with lanes while only this halo is here)" };
const FROM: Record<string, string> = { yours: "yours", packs: "a pack", shipped: "shipped with Halo" };

/** The newest receipt of square `ref` in this halo's sessions, its count, and the live one (as one stable string). */
function receipts(ref: string) {
  return (s: Parameters<typeof allAgents>[0]): string => {
    const hits = allAgents(s).filter((r) => r.h.local && r.a.square?.name === ref);
    if (!hits.length) return "";
    const last = hits.reduce((b, r) => ((Number(r.a.since) || 0) > (Number(b.a.since) || 0) ? r : b));
    const lit = hits.find((r) => isLive(r.a));
    const caller = lit ? (lit.s.agents || []).find((a) => a.agent_id === lit.a.parent) : undefined;
    return JSON.stringify({ n: hits.length, since: last.a.since, cost: last.a.cost_usd, state: last.a.state,
                            lit: lit ? { by: caller?.name || lit.a.parent || "main", need: lit.a.task || "", since: lit.a.since } : null });
  };
}

type Got = { n: number; since: number; cost: number; state: string; lit: { by: string; need: string; since: number } | null };

export function SquareHover({ sqRef, row = false }: { sqRef: string; row?: boolean }) {
  const q = useWf((s) => squareOf(s, sqRef));
  const raw = useFleet(receipts(sqRef));
  const got: Got | null = raw ? JSON.parse(raw) : null;
  const now = useNow(!!got?.lit, 1000);
  if (!q) return null;
  const file = q.path ? q.path.split(/[\\/]/).pop() : "";
  const from = q.group === "packs" ? `pack ${q.origin.replace(/^pack:?/, "") || "?"}` : q.group === "yours" && /project/.test(q.origin) ? "the project" : FROM[q.group] || q.origin;
  const lead = q.lead ? `${q.lead.bio} on ${q.lead.model || "the session's model"}` : typeof q.lineup === "string" ? `lineup ${q.lineup}` : "the session's lineup";
  const last = got ? joined([ago(got.since), spent(got.cost), got.state, `${plural(got.n, "run")} in all`]) : "";
  const rows: HoverRow[] = [
    ["Takes", q.takes.join(", ") || "text"],
    ["Gives", q.gives.join(", ") || (q.square ? "" : "nothing: not a square, the router never picks it")],
    // 3.3.16.3: on the board, its line's rule (which says what it covers) in place of the covers
    q.enabled ? ["When", q.when_mode === "off" ? "not connected: main never uses it" : q.when_sentence || q.covers.join(", ")] : ["Covers", q.covers.join(", ")],
    ["Runs on", joined([lead, ENGINE[q.engine] || q.engine])],
    ["Costs", q.costs], // its band and cap, in the contract's words
    ["Limits", q.limits],
    ["From", joined([from, file])],
    ["Last run", last],
  ];
  const held = got?.lit ? since(got.lit.since, now) : null;
  const lit = got?.lit ? joined([`called by ${got.lit.by}`, got.lit.need && `need: ${got.lit.need}`, held != null && `for ${span(held)}`]) : "";
  return (
    <HoverBody title={q.ref} is={q.does || ""} rows={rows} now={lit}
               foot={row ? "Drag it onto the board to enable it; a click on its board card opens everything" : "Click: its contract in the inspector"} />
  );
}
