// Roles Live's pieces (3.3.11.0 R2): a node (name, role, state, model, cost, elapsed, the pick's reason or
// what it does now; its glow from live.ts's rules; a "steer" chip and a "..." menu), the "unknown parent" node and a
// lineup card's faint group. 3.3.15.0 L1, the Instrument look (styles/nodes.css): the model without its provider
// prefix (the full id in the tooltip and the Inspector), a fade-in for a node born after the page drew, a failed
// node's red kept until it is clicked, the selected / hovered outline. 3.3.16.0 R2 "the Fleet fold": the one agent
// node -- what the Fleet Map's node had that it lacked came with it: the running tool and how long it has run
// (`roles-live-tool`), the cost counting up (`roles-live-cost`), the pin, the Steer box's target (`data-target`, in
// Session's Map), the state's motion; a click is the caller's (Live selects, Session's Map picks the steer's target),
// a double-click opens the agent panel. The bar is routes/agents/live/LiveBar.tsx.
import type { KeyboardEvent, MouseEvent } from "react";
import { shortModel } from "../../lib/modelName";
import { ackFailed, failedAcked, useBorn } from "../../lib/motion/born";
import { Icon, toolIcon } from "../../lib/ui";
import { agentMotion, findAgent, fleet, useFleet } from "../fleet/store";
import { openAgentPanel } from "../fleet/actions";
import { cost, short } from "../orchestra/format";
import type { MenuAt } from "../agents/live/NodeMenu";
import { useTicker, useToolClock } from "../agents/live/nodeBits";
import { steerAgent, useTargetKey } from "../session/steer";
import { SquareRow } from "../agents/live/SquareRow"; // 3.3.16.0 R3: a square's agent
import type { LiveBox, LiveGroup } from "./liveLayout";

function took(n: LiveBox["node"], now: number): string {
  if (!n.started) return "";
  const s = Math.max(0, Math.round((n.ended ? n.ended * 1000 : now) / 1000 - n.started));
  return s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

function nowLine(n: LiveBox["node"]): string {
  if (n.state === "waiting") return "waits on you";
  if (n.state === "paused") return "paused: holds at its next step";
  return n.current && n.current !== "thinking" ? n.current : n.task || n.current || "";
}

type Props = { b: LiveBox; selected: boolean; now: number; onMenu: (m: MenuAt) => void; onPick: (key: string) => void };

export function LiveNodeCard({ b, selected, now, onMenu, onPick }: Props) {
  const n = b.node;
  const style = { left: b.x, top: b.y, width: b.w, height: b.h };
  const [born, grown] = useBorn(); // 3.3.15.0 L1: a node that appears after the page drew fades in once
  const hovered = useFleet((s) => !!n.key && s.hover === n.key); // a Live line hovered elsewhere: the same outline
  const pinned = useFleet((s) => !!n.key && s.pinned === n.key);
  const doneAt = useFleet((s) => s.doneAt[n.key] || 0);
  const act = useFleet((s) => s.activity[n.key]);
  const row = n.key ? findAgent(fleet.get(), n.key)?.a : undefined;
  const clock = useToolClock(n.key, row, act);
  const shown = useTicker(Number(n.cost) || 0);
  const target = useTargetKey() === n.key && !!n.key;
  if (n.virtual)
    return (
      <div className="rlm-node rlm-virtual" style={style} data-testid="roles-live-unknown" title={n.task}>
        <b className="rlm-name">unknown parent</b>
        <div className="muted rlm-line">{n.task}</div>
      </div>
    );
  const failed = n.glow === "failed";
  const open = () => (failed && ackFailed(n.key), onPick(n.key));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open());
  const menu = (e: MouseEvent) => (e.stopPropagation(), onMenu({ x: e.clientX, y: e.clientY, key: n.key }));
  const rest = clock.tool && row?.current?.includes(":") ? " · " + row.current.split(":").slice(1).join(":").trim() : "";
  return (
    <div className="rlm-node" style={style} role="button" tabIndex={0} onClick={open} onKeyDown={onKey} onDoubleClick={() => openAgentPanel(n.key)}
         data-testid="roles-live-node" data-agent={n.key ? n.key.split("|").slice(2).join("|") : n.id} data-key={n.key} data-state={n.state} data-glow={n.glow || undefined}
         data-motion={row ? agentMotion(row, doneAt) : undefined} data-parent={n.parent || undefined} data-harness={n.harness || undefined}
         data-card={n.card || undefined} data-selected={selected || undefined} data-target={target || undefined} aria-label={`${n.name}: ${n.state}`}
         data-born={born || undefined} onAnimationEnd={(e) => e.target === e.currentTarget && grown()}
         data-ack={(failed && failedAcked(n.key)) || undefined} data-hover={hovered || undefined}>
      {target && <span className="rlm-target" data-testid="roles-live-target" aria-hidden="true" />}
      <div className="rlm-head">
        <span className="rlm-dot" aria-hidden="true" />
        <b className="rlm-name">{short(n.name, 22)}</b>
        {n.role && n.role !== n.name && <span className="og-chip mono rlm-role">{short(n.role, 14)}</span>}
        <span className="spacer" />
        {pinned && <span className="rlm-pin" data-testid="roles-live-pin" title="Pinned: its mini stream stays on screen"><Icon name="pin" size={12} /></span>}
        <span className="og-badge mono" data-live={n.activity || undefined}>{n.state || "?"}</span>
        <button className="rlm-more" onClick={menu} onDoubleClick={(e) => e.stopPropagation()} aria-label={`${n.name}: more`} title="Steer, pause, pin, stop..." data-testid="roles-live-more">...</button>
      </div>
      <div className="mono muted rlm-line" title={n.model || undefined}>
        <span data-testid="roles-live-model">{short(shortModel(n.model) || "model ?", 30)}</span> · <span data-testid="roles-live-cost">{cost(shown)}</span>
        {n.started ? ` · ${took(n, now)}` : ""}
      </div>
      {n.square ? <SquareRow n={n} /> : clock.tool ? (
        <div className="mono rlm-line rlm-tool" data-testid="roles-live-tool" data-tool={clock.tool} data-secs={clock.secs ?? undefined} title={row?.current || clock.tool}>
          <Icon name={toolIcon(clock.tool)} size={11} /><span className="rlm-tool-text">{short(clock.text + rest, 52)}</span>
        </div>
      ) : n.pick ? (
        <div className="mono rlm-pick" title={n.pick} data-testid="roles-live-pick">{n.pick}</div>
      ) : (
        <div className="muted rlm-line" title={nowLine(n)}>{short(nowLine(n), 60)}</div>
      )}
      <button className="rlm-steer mono" onClick={(e) => (e.stopPropagation(), steerAgent(n.key))} onDoubleClick={(e) => e.stopPropagation()}
              title={`Steer ${n.name}: the Steer box, addressed to it`} data-testid="roles-live-steer">steer ▸</button>
    </div>
  );
}

export function LiveGroupBox({ g }: { g: LiveGroup }) {
  return (
    <div className="rlm-group" style={{ left: g.x, top: g.y, width: g.w, height: g.h }} data-testid="roles-live-group" data-card={g.card}
         title={`lineup card ${g.label}: ${g.count} agent${g.count === 1 ? "" : "s"} here run under it`}>
      <span className="rlm-group-label mono">{g.label}</span>
    </div>
  );
}
