// A Live agent box's hover card (3.3.16.1): its role (else its name), the task it was given, and what GET fleet and the
// feed already hold -- its name and bio, its state and for how long, its full model id with what it takes, its cost with
// tokens and turns, who started it and how many it started, the Auto pick's reason, the claims it holds on a run -- then
// NOW: the running tool with its time, else its last line. A click selects it: the agent inspector.
import { findAgent, useFleet, useNow } from "../../fleet/store";
import { useOrch } from "../../orchestra/store";
import { modelRow, useRoles } from "../../roles/store";
import type { LiveNode } from "../../roles/liveModel";
import { useToolClock } from "../live/nodeBits";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { joined, plural, since, span, spent, takesWords, tokens } from "./words";

const LIVE = ["queued", "running", "waiting", "paused"];

export function AgentHover({ k, n }: { k: string; n: LiveNode }) {
  const a = useFleet((s) => findAgent(s, k)?.a);
  const sess = useFleet((s) => findAgent(s, k)?.s);
  const act = useFleet((s) => s.activity[k]);
  const takes = useRoles((s) => modelRow(s, String(a?.model || n.model))?.takes);
  const claims = useOrch((s) => s.data?.claims);
  const state = String(a?.state || n.state || "");
  const now = useNow(LIVE.includes(state), 1000);
  const clock = useToolClock(k, a, act);
  const name = String(a?.name || n.name);
  const role = String(a?.role || n.role || "");
  const model = String(a?.model || n.model || "");
  const agents = sess?.agents || [];
  const parent = a?.parent ? agents.find((x) => x.agent_id === a.parent) : undefined;
  const kids = a ? agents.filter((x) => x.parent === a.agent_id).length : 0;
  const owns = claims ? [...new Set(claims.filter((c) => c.holder === name).map((c) => c.key))] : [];
  const held = since(a?.since ?? n.started, now);
  const ended = !LIVE.includes(state);
  const rows: HoverRow[] = [
    ["Agent", joined([name, a?.bio && a.bio !== name && `bio ${a.bio}`])],
    ["State", joined([state, !ended && held != null && `for ${span(held)}`])],
    ["Model", joined([model, takesWords(takes) && `takes ${takesWords(takes)}`])],
    ["Cost", joined([spent(a?.cost_usd ?? n.cost), tokens(a?.tokens_in, a?.tokens_out), !!a?.turns && plural(Number(a.turns), "turn")])],
    ["Started by", parent ? String(parent.name || parent.agent_id) : ""],
    ["Has started", kids ? plural(kids, "agent") : ""],
    ["Picked because", String(a?.model_reason || "")],
    ["Owns", owns.join(", ")],
  ];
  const rest = clock.tool && a?.current?.includes(":") ? a.current.split(":").slice(1).join(":").trim() : "";
  const line = clock.tool ? joined([clock.text, rest]) : state === "waiting" ? "waits on you" : state === "paused" ? "paused: holds at its next step"
    : String(a?.last_text || (a?.current && a.current !== "thinking" ? a.current : "") || "");
  return (
    <HoverBody title={role && role !== name ? role : name} is={String(a?.task || n.task || "")} rows={rows} now={ended ? "" : line}
               foot="Click: this agent in the inspector" />
  );
}
