// The pieces of the Roles canvas (3.0.7.0 R2): an agent card (name, role,
// scope badge, the instances stack, the model pill with its price in / out
// and context, a gym score when the gym measured it, a warnings badge, and
// the live badge while an agent works under it), a tier box (its label strip
// collapses and expands it), and the delegation / pipeline edges
// the classic canvas drew (a delegation edge names its routing words while
// one of its cards is selected). Cards and boxes are memoised. 3.1.5.0 R3:
// the holo look -- the card's state glyph and live badge open the glow's
// legend on hover (GlowLegend.tsx), a done glow fades over ten seconds (the
// fade resumes where it is when the card draws again), the selected card and
// every tier box wear the HUD brackets, and a tier box and the edges into a
// card take the same state colour (working cyan, waiting amber, done green,
// failed red).
import { memo, useRef, type CSSProperties, type PointerEvent } from "react";
import { cost } from "../orchestra/format";
import { CARD_H, CARD_W, edgePath, type Box } from "./layout";
import { glowOf, hideLegend, showLegend, type GlowState } from "./glow";
import { focusModel } from "./modelActions";
import { priceText, scopeLabel } from "./store";
import type { GraphEdge, GraphNode, GymScore, LiveAgent, ModelRow, Pos, Tier } from "./types";

const STATE_LABEL: Record<string, string> = { typing: "typing", working: "working", waiting: "waits on you", done: "done", failed: "failed", queued: "queued" };
const GLYPH: [RegExp, string][] = [[/^(Edit|Write|MultiEdit|NotebookEdit)/, "✎"], [/^(Bash|PowerShell|Shell)/, "›_"], [/^(Read|Glob|LS)/, "▤"], [/^(Grep|Search)/, "⌕"], [/^(Agent|Task|SendMessage)/, "◉"], [/^Web/, "◍"]];
export const glyph = (tool: string) => GLYPH.find(([re]) => re.test(tool))?.[1] || "•";

type CardProps = {
  n: GraphNode;
  x: number;
  y: number;
  model: ModelRow | undefined;
  gym: GymScore | undefined;
  issues: number;
  selected: boolean;
  dragging: boolean;
  live: LiveAgent[];
  activity: string;
  onDown: (ev: PointerEvent<HTMLElement>, id: string) => void;
};

const STATE_GLYPH: Record<string, string> = { working: "●", waiting: "◆", done: "✓", failed: "✕" };
const legendOn = (state: GlowState | "", card: string) => ({
  onMouseEnter: (e: { currentTarget: HTMLElement }) => showLegend(e.currentTarget, state, card),
  onMouseLeave: hideLegend,
});

function LiveBadge({ list, activity, card }: { list: LiveAgent[]; activity: string; card: string }) {
  const lead = list.find((a) => a.activity === activity) || list[0];
  const usd = list.reduce((s, a) => s + (Number(a.cost_usd) || 0), 0);
  return (
    <div className="rc-live mono" data-testid="roles-live-badge" {...legendOn(glowOf(activity), card)}>
      {activity === "tool" && lead.tool ? (
        <span className="rc-live-tool" title={lead.current || lead.tool}>{glyph(lead.tool)} {lead.tool}</span>
      ) : activity === "waiting" ? (
        <span className="rc-live-diamond" title="waits on you">◆</span>
      ) : (
        <span className="rc-live-state">{STATE_LABEL[activity] || activity}</span>
      )}
      {list.length > 1 && <span className="rc-live-count" title={`${list.length} agents on this card`}>×{list.length}</span>}
      <span className="rc-live-cost">{cost(usd)}</span>
    </div>
  );
}

export const Card = memo(function Card({ n, x, y, model, gym, issues, selected, dragging, live, activity, onDown }: CardProps) {
  const stack = Math.min(3, Math.max(1, n.instances || 1));
  const lead = live.find((a) => a.activity === activity);
  const glow = glowOf(activity);
  const ended = glow === "done" ? Math.max(0, ...live.filter((a) => a.activity === "done").map((a) => a.endedAt || 0)) : 0;
  // the fade resumes where it is when the card first draws done (its delay is fixed then, so a later draw never jumps it)
  const fadeRef = useRef<{ ended: number; delay: string }>({ ended: 0, delay: "0s" });
  if (ended && fadeRef.current.ended !== ended) fadeRef.current = { ended, delay: `${-Math.min(10, (Date.now() - ended) / 1000).toFixed(2)}s` };
  const fade = ended ? ({ "--rc-fade": fadeRef.current.delay } as CSSProperties) : {};
  return (
    <article
      className="rc-card"
      style={{ left: x, top: y, width: CARD_W, height: CARD_H, ...fade }}
      data-testid="roles-card"
      data-id={n.id}
      data-role={n.role}
      data-agent={n.agent}
      data-selected={selected || undefined}
      data-dragging={dragging || undefined}
      data-live={activity || undefined}
      data-glow={glow || undefined}
      data-holo-state={glow || undefined}
      data-pulse={lead ? (lead.calls % 2 ? "b" : "a") : undefined}
      data-stack={stack > 1 ? stack : undefined}
      aria-label={`${n.agent}, ${n.role}${n.alias ? " as " + n.alias : ""}`}
      title="Drag to move; drop into another tier box to move it there. Arrows nudge it, Delete removes it."
      onPointerDown={(ev) => onDown(ev, n.id)}
    >
      <span className="rc-band" aria-hidden="true" />
      {selected && <span className="holo-tlbr" aria-hidden="true" />}
      {selected && <span className="holo-corners" aria-hidden="true" />}
      <header className="rc-head">
        {glow && (
          <span className="rc-glyph" data-testid="roles-card-glyph" data-state={glow} aria-label={`glow: ${glow}`} {...legendOn(glow, n.id)}>{STATE_GLYPH[glow]}</span>
        )}
        <b className="rc-agent">{n.agent || "(no agent)"}</b>
        <span className="rc-scope mono" data-scope={n.scope || "none"} title={n.scope === "template" ? "This bio ships with Halo: Duplicate it in the Bios panel for an editable copy" : `This bio lives in your ${n.scope} scope`}>
          {scopeLabel(n.scope)}
        </span>
      </header>
      <div className="rc-role">
        {n.role}
        {n.alias && n.alias !== n.role ? ` · as ${n.alias}` : ""}
        {n.instances > 1 && <span className="rc-inst mono" title={`${n.instances} instances of this slot`}> ×{n.instances}</span>}
      </div>
      <button type="button" className="rc-model mono" data-testid="roles-model-pill" onClick={() => focusModel(n.id)}
              title={`${n.model ? `${n.model}${n.fallback ? " · fallback " + n.fallback : ""}` : "no model resolves for this slot"}: click to change it (the Inspector's MODEL strip)`}>
        {n.model ? n.model.replace(/^or:[^/]+\//, "") : "no model resolves"}
      </button>
      <div className="rc-meta mono">
        <span title="price per 1M tokens in / out">{priceText(model)}</span>
        <span>ctx {model?.context || n.context || "?"}</span>
        {gym && <span className="rc-gym" title={`gym score on this machine${gym.tokens_per_second ? `, ${Math.round(gym.tokens_per_second)} tok/s` : ""}`}>gym {gym.score.toFixed(2)}</span>}
      </div>
      {issues > 0 && <span className="rc-warn mono" data-testid="roles-card-warn" title={[...n.problems, ...n.warnings].join("\n") || "see the Problems panel"}>{issues}</span>}
      {activity && <LiveBadge list={live} activity={activity} card={n.id} />}
    </article>
  );
});

type TierProps = {
  t: Tier;
  b: Box;
  count: number;
  collapsed: boolean;
  hot: boolean;
  /** The strongest glow of its cards (working, waiting, done, failed), "" for none. */
  state: GlowState | "";
  onToggle: (name: string) => void;
};

export const TierBox = memo(function TierBox({ t, b, count, collapsed, hot, state, onToggle }: TierProps) {
  return (
    <div className="rc-tier holo-frame" data-testid="roles-tier" data-tier={t.name} data-index={t.index} data-implicit={t.implicit || undefined}
         data-collapsed={collapsed || undefined} data-hot={hot || undefined} data-holo-state={state || undefined} style={{ left: b.x, top: b.y, width: b.w, height: b.h }}>
      <span className="holo-corners" aria-hidden="true" />
      <button className="rc-tier-head" onClick={() => onToggle(t.name)} aria-expanded={!collapsed} data-testid="roles-tier-toggle"
              title={collapsed ? "Expand this tier" : "Collapse this tier to its label"}>
        <span className="rc-tier-caret" aria-hidden="true">{collapsed ? "▸" : "▾"}</span>
        <span className="rc-tier-label">Tier {t.index} · {t.name}</span>
        <span className="rc-tier-count mono">
          {count}
          {t.max_parallel ? ` · max ${t.max_parallel}` : ""}
          {t.implicit ? " · implicit" : ""}
        </span>
      </button>
    </div>
  );
});

export function Edges({ edges, pos, hidden, w, h, sel, lit, glows }: { edges: GraphEdge[]; pos: Record<string, Pos>; hidden: Set<string>; w: number; h: number; sel: string; lit: Set<string>; glows: Record<string, GlowState | ""> }) {
  return (
    <svg className="rc-edges" width={w} height={h} aria-hidden="true">
      <defs>
        {(["delegation", "pipeline"] as const).map((k) => (
          <marker key={k} id={`rc-arrow-${k}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className={`rc-arrow rc-arrow-${k}`} />
          </marker>
        ))}
      </defs>
      {edges.map((e, i) => {
        const a = pos[e.from], b = pos[e.to];
        if (!a || !b || hidden.has(e.from) || hidden.has(e.to)) return null;
        const { d, mx, my } = edgePath(a, b);
        const on = sel === e.from || sel === e.to;
        return (
          <g key={`${e.kind}-${e.from}-${e.to}-${i}`} className="rc-edge-g" data-kind={e.kind}>
            <path className="rc-edge" data-kind={e.kind} data-on={on || undefined} data-lit={lit.has(e.to) || undefined} data-state={glows[e.to] || undefined}
                  data-to={e.to} d={d} markerEnd={`url(#rc-arrow-${e.kind})`} data-testid="roles-edge" />
            {e.label && (on || e.kind !== "delegation") && <text className="rc-edge-label" x={mx} y={my} textAnchor="middle">{e.label}</text>}
          </g>
        );
      })}
    </svg>
  );
}
