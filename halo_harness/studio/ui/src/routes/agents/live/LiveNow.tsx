// The line under Live's bar (3.3.18.0 "The living canvas" part 3): the one sentence of what is going on right now
// (narrate.ts), what waits on you first, then the agents at work by block or group, then what the session waits on --
// with the wait's running seconds and the session's elapsed time beside it (they tick; the sentence does not). Hover: a
// row per block or group (its agents, their state, models and cost). A click centres the agent the session waits on.
// Nothing when nothing runs (the empty state says it).
import { useHover } from "../../../lib/hover/useHover";
import { HoverBody } from "../../../lib/hover/HoverBody";
import type { LiveNode } from "../../roles/liveModel";
import { narrate } from "./narrate";
import type { PlanGeometry } from "./planLayout";
import { useWaits } from "./useWaits";
import { secsWords } from "./waits";

/** Scroll the canvas so the node of `id` sits in its middle. */
export function centreNode(id: string): boolean {
  const el = [...document.querySelectorAll<HTMLElement>('[data-testid="roles-live-map"]:not([data-scope="thumb"]) [data-testid="roles-live-node"]')]
    .find((x) => x.dataset.agent === id || x.dataset.key?.endsWith("|" + id));
  if (!el) return false;
  el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
  return true;
}

type Props = { nodes: LiveNode[]; now: number; on: boolean; plan: PlanGeometry | null };

export function LiveNow({ nodes, now, on, plan }: Props) {
  const { waits, path } = useWaits(nodes, now, on);
  const block = new Map<string, string>();
  for (const b of plan?.blocks || []) for (const m of b.members) block.set(m.id, b.def.title);
  const where = (n: LiveNode) => (plan ? block.get(n.id) || "" : n.group?.title || "");
  const s = narrate(nodes, waits, path, where);
  const hv = useHover("group", "live-narration", () => <HoverBody title="What is going on now" is="Each block or group: its agents at work, what waits on you, their models and what they cost." rows={s.rows} foot="A click centres the agent the session waits on" />, on && !!s.text);
  if (!on || !s.text) return null;
  const secs = s.waitText && path.wait ? secsWords(path.wait.since, now) : "";
  const started = Math.min(...nodes.map((n) => n.started || Infinity));
  const mins = isFinite(started) ? Math.floor(Math.max(0, now / 1000 - started) / 60) : null;
  const leaf = path.leaf;
  return (
    <div className="lv-narr mono" role="button" tabIndex={0} data-density="bar" data-testid="live-narration" data-text={s.text} data-wait={path.wait?.kind || undefined}
         data-leaf={leaf ? leaf.key.split("|").slice(2).join("|") || leaf.id : undefined}
         onClick={() => leaf && centreNode(leaf.key.split("|").slice(2).join("|") || leaf.id)}
         onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && leaf && (e.preventDefault(), centreNode(leaf.key.split("|").slice(2).join("|") || leaf.id))}
         title={hv.titles ? `${s.text} (a click centres ${leaf?.name || "the agent it waits on"})` : undefined} {...hv.props}>
      <span className="lv-narr-text">{s.head}{secs && <span className="lv-narr-secs" data-testid="live-wait-secs">, {secs}</span>}{s.tail}</span>
      {mins !== null && <span className="lv-narr-clock muted" data-testid="live-narration-clock">{mins ? `${mins} min` : "under a minute"}</span>}
    </div>
  );
}
