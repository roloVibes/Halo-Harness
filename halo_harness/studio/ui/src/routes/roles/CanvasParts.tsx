// The pieces of the Roles canvas (3.0.7.0 R2): an agent card (name, role,
// scope badge, the instances stack, the model pill with its price in / out
// and context, a gym score when the gym measured it, a warnings badge, and
// the live badge while an agent works under it), a tier box (its label strip
// collapses and expands it), and the delegation / pipeline edges
// the classic canvas drew (a delegation edge names its routing words while
// one of its cards is selected). Cards and boxes are memoised.
import { memo, type PointerEvent } from "react";
import { cost } from "../orchestra/format";
import { CARD_H, CARD_W, edgePath, type Box } from "./layout";
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

function LiveBadge({ list, activity }: { list: LiveAgent[]; activity: string }) {
  const lead = list.find((a) => a.activity === activity) || list[0];
  const usd = list.reduce((s, a) => s + (Number(a.cost_usd) || 0), 0);
  return (
    <div className="rc-live mono" data-testid="roles-live-badge">
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
  return (
    <article
      className="rc-card"
      style={{ left: x, top: y, width: CARD_W, height: CARD_H }}
      data-testid="roles-card"
      data-id={n.id}
      data-role={n.role}
      data-agent={n.agent}
      data-selected={selected || undefined}
      data-dragging={dragging || undefined}
      data-live={activity || undefined}
      data-pulse={lead ? (lead.calls % 2 ? "b" : "a") : undefined}
      data-stack={stack > 1 ? stack : undefined}
      aria-label={`${n.agent}, ${n.role}${n.alias ? " as " + n.alias : ""}`}
      title="Drag to move; drop into another tier box to move it there. Arrows nudge it, Delete removes it."
      onPointerDown={(ev) => onDown(ev, n.id)}
    >
      <span className="rc-band" aria-hidden="true" />
      <header className="rc-head">
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
      <div className="rc-model mono" data-testid="roles-model-pill" title={n.model ? `${n.model}${n.fallback ? " · fallback " + n.fallback : ""}` : "no model resolves for this slot"}>
        {n.model ? n.model.replace(/^or:[^/]+\//, "") : "no model resolves"}
      </div>
      <div className="rc-meta mono">
        <span title="price per 1M tokens in / out">{priceText(model)}</span>
        <span>ctx {model?.context || n.context || "?"}</span>
        {gym && <span className="rc-gym" title={`gym score on this machine${gym.tokens_per_second ? `, ${Math.round(gym.tokens_per_second)} tok/s` : ""}`}>gym {gym.score.toFixed(2)}</span>}
      </div>
      {issues > 0 && <span className="rc-warn mono" data-testid="roles-card-warn" title={[...n.problems, ...n.warnings].join("\n") || "see the Problems panel"}>{issues}</span>}
      {activity && <LiveBadge list={live} activity={activity} />}
    </article>
  );
});

type TierProps = {
  t: Tier;
  b: Box;
  count: number;
  collapsed: boolean;
  hot: boolean;
  onToggle: (name: string) => void;
};

export const TierBox = memo(function TierBox({ t, b, count, collapsed, hot, onToggle }: TierProps) {
  return (
    <div className="rc-tier" data-testid="roles-tier" data-tier={t.name} data-index={t.index} data-implicit={t.implicit || undefined}
         data-collapsed={collapsed || undefined} data-hot={hot || undefined} style={{ left: b.x, top: b.y, width: b.w, height: b.h }}>
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

export function Edges({ edges, pos, hidden, w, h, sel, lit }: { edges: GraphEdge[]; pos: Record<string, Pos>; hidden: Set<string>; w: number; h: number; sel: string; lit: Set<string> }) {
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
            <path className="rc-edge" data-kind={e.kind} data-on={on || undefined} data-lit={lit.has(e.to) || undefined} d={d} markerEnd={`url(#rc-arrow-${e.kind})`} data-testid="roles-edge" />
            {e.label && (on || e.kind !== "delegation") && <text className="rc-edge-label" x={mx} y={my} textAnchor="middle">{e.label}</text>}
          </g>
        );
      })}
    </svg>
  );
}
