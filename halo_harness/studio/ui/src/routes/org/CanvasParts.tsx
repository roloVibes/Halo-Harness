// The pieces of the Org canvas (3.0.7.0 R3): an agent card (title, role,
// adapter, status and spend against its budget), a group box with its label
// strip (drag the strip to move the whole group), and the reports-to edges.
// Cards and boxes are memoised: a poll that changed one agent redraws that
// card only.
import { memo, type PointerEvent } from "react";
import { usd } from "./store";
import { boxOf, CARD_H, CARD_W, type Group } from "./layout";
import type { Agent, Pos } from "./types";

type CardProps = {
  a: Agent;
  x: number;
  y: number;
  selected: boolean;
  dragging: boolean;
  onDown: (ev: PointerEvent<HTMLElement>, id: string) => void;
  onOpen: (id: string) => void;
};

export const Card = memo(function Card({ a, x, y, selected, dragging, onDown, onOpen }: CardProps) {
  const status = String(a.status || "idle");
  const bio = a.metadata?.halo_agent;
  return (
    <article
      className="oc-card"
      style={{ left: x, top: y, width: CARD_W, height: CARD_H }}
      data-testid="org-card"
      data-id={a.id}
      data-status={status}
      data-selected={selected || undefined}
      data-dragging={dragging || undefined}
      aria-label={`${a.name}, ${a.role || "agent"}, ${status}`}
      title="Drag to move; drop into another box (or onto a card) to change who it reports to. Double-click: the Inspector."
      onPointerDown={(ev) => onDown(ev, a.id)}
      onDoubleClick={() => onOpen(a.id)}
    >
      <header className="oc-card-head">
        <span className="oc-dot" aria-hidden="true" />
        <b className="oc-name">{a.name}</b>
        <span className="oc-status mono">{status}</span>
      </header>
      <div className="oc-sub">{[a.role, a.title].filter(Boolean).join(" · ") || "agent"}</div>
      <div className="oc-foot mono">
        <span className="oc-chip">{a.adapterType || "?"}{bio ? " · halo " + bio : ""}</span>
        <span className="oc-spend" title="spent this month / monthly budget">
          {usd(a.spentMonthlyCents)}
          {a.budgetMonthlyCents ? " / " + usd(a.budgetMonthlyCents, 0) : ""}
        </span>
      </div>
      {a.errorReason && <span className="oc-warn" title={String(a.errorReason)}>!</span>}
    </article>
  );
});

type BoxProps = { g: Group; pos: Record<string, Pos>; hot: boolean; onDown: (ev: PointerEvent<HTMLElement>, g: Group) => void };

export const GroupBox = memo(function GroupBox({ g, pos, hot, onDown }: BoxProps) {
  const b = boxOf(g, pos);
  if (!b) return null;
  return (
    <div className="oc-group" data-testid="org-group" data-key={g.key} data-top={g.key === "top" || undefined} data-hot={hot || undefined}
         style={{ left: b.x, top: b.y, width: b.w, height: b.h }}>
      <div className="oc-group-head" onPointerDown={(ev) => onDown(ev, g)} title="Drag to move the whole group">
        <span className="oc-group-label">{g.label}</span>
        <span className="oc-group-count mono">{g.members.length}</span>
      </div>
    </div>
  );
});

export function Edges({ agents, pos, w, h, sel }: { agents: Agent[]; pos: Record<string, Pos>; w: number; h: number; sel: string }) {
  return (
    <svg className="oc-edges" width={w} height={h} aria-hidden="true">
      {agents.map((a) => {
        const p = pos[a.id];
        const m = a.reportsTo ? pos[a.reportsTo] : undefined;
        if (!p || !m) return null;
        const x1 = m.x + CARD_W / 2, y1 = m.y + CARD_H, x2 = p.x + CARD_W / 2, y2 = p.y;
        const bend = Math.max(24, Math.abs(y2 - y1) / 2);
        const d = `M${x1} ${y1} C${x1} ${y1 + bend} ${x2} ${y2 - bend} ${x2} ${y2}`;
        return <path key={a.id} className="oc-edge" data-on={sel === a.id || sel === a.reportsTo || undefined} d={d} data-testid="org-edge" />;
      })}
    </svg>
  );
}
