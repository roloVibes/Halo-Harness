// Roles Live's pieces (3.3.11.0 R2): a node (name, role, state, model, cost, elapsed, the pick's reason or
// what it does now; its glow from live.ts's rules; a "steer" chip and a "..." menu as the Map's node has),
// the "unknown parent" node, a lineup card's faint group, and the bar (Plan | Live, the session picker, the
// density, the counts, Fit and the zoom). 3.3.15.0 L1, the Instrument look (styles/nodes.css): the model without
// its provider prefix (the full id in the tooltip and the Inspector), a fade-in for a node born after the page
// drew, a failed node's red kept until it is clicked, the selected / hovered outline.
import type { KeyboardEvent, MouseEvent } from "react";
import { shortModel } from "../../lib/modelName";
import { ackFailed, failedAcked, useBorn } from "../../lib/motion/born";
import { Button } from "../../lib/ui";
import { useFleet } from "../fleet/store";
import { cost, short } from "../orchestra/format";
import type { MenuAt } from "../fleet/MapNode";
import { steerAgent } from "../session/steer";
import type { RecordRef } from "../../lib/work/record";
import { PlanLive } from "./CanvasBar";
import type { Density, LiveBox, LiveGroup } from "./liveLayout";
import { selectLive } from "./liveModel";
import { roles, useRoles } from "./store";

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

export function LiveNodeCard({ b, selected, now, onMenu }: { b: LiveBox; selected: boolean; now: number; onMenu: (m: MenuAt) => void }) {
  const n = b.node;
  const style = { left: b.x, top: b.y, width: b.w, height: b.h };
  const [born, grown] = useBorn(); // 3.3.15.0 L1: a node that appears after the page drew fades in once
  const hovered = useFleet((s) => !!n.key && s.hover === n.key); // a Live line hovered elsewhere: the same outline
  if (n.virtual)
    return (
      <div className="rlm-node rlm-virtual" style={style} data-testid="roles-live-unknown" title={n.task}>
        <b className="rlm-name">unknown parent</b>
        <div className="muted rlm-line">{n.task}</div>
      </div>
    );
  const failed = n.glow === "failed";
  const open = () => (failed && ackFailed(n.key), selectLive(n.key));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open());
  const menu = (e: MouseEvent) => (e.stopPropagation(), onMenu({ x: e.clientX, y: e.clientY, key: n.key }));
  return (
    <div className="rlm-node" style={style} role="button" tabIndex={0} onClick={open} onKeyDown={onKey}
         data-testid="roles-live-node" data-agent={n.id} data-key={n.key} data-state={n.state} data-glow={n.glow || undefined}
         data-card={n.card || undefined} data-selected={selected || undefined} aria-label={`${n.name}: ${n.state}`}
         data-born={born || undefined} onAnimationEnd={(e) => e.target === e.currentTarget && grown()}
         data-ack={(failed && failedAcked(n.key)) || undefined} data-hover={hovered || undefined}>
      <div className="rlm-head">
        <span className="rlm-dot" aria-hidden="true" />
        <b className="rlm-name">{short(n.name, 22)}</b>
        {n.role && n.role !== n.name && <span className="og-chip mono rlm-role">{short(n.role, 14)}</span>}
        <span className="spacer" />
        <span className="og-badge mono" data-live={n.activity || undefined}>{n.state || "?"}</span>
        <button className="rlm-more" onClick={menu} aria-label={`${n.name}: more`} title="Steer, pause, pin, stop..." data-testid="roles-live-more">...</button>
      </div>
      <div className="mono muted rlm-line" title={n.model || undefined} data-testid="roles-live-model">{short(shortModel(n.model) || "model ?", 30)} · {cost(n.cost)}{n.started ? ` · ${took(n, now)}` : ""}</div>
      {n.pick ? (
        <div className="mono rlm-pick" title={n.pick} data-testid="roles-live-pick">{n.pick}</div>
      ) : (
        <div className="muted rlm-line" title={nowLine(n)}>{short(nowLine(n), 60)}</div>
      )}
      <button className="rlm-steer mono" onClick={(e) => (e.stopPropagation(), steerAgent(n.key))} title={`Steer ${n.name}: the Steer box, addressed to it`}
              data-testid="roles-live-steer">steer ▸</button>
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

type BarProps = { refs: RecordRef[]; sid: string; agents: number; live: number; zoom: number; setZoom: (z: number) => void; fit: () => void };

export function LiveBar({ refs, sid, agents, live, zoom, setZoom, fit }: BarProps) {
  const density = useRoles((s) => s.liveDensity);
  const setDensity = (d: Density) => roles.update(() => ({ liveDensity: d }));
  const here = refs.find((r) => r.id === sid);
  return (
    <div className="rc-bar rlm-bar">
      <PlanLive />
      {refs.length > 1 ? (
        <select className="input mono rlm-pick-session" value={sid} onChange={(e) => roles.update(() => ({ liveSid: e.target.value }))}
                aria-label="The session Live draws" data-testid="roles-live-session">
          {refs.map((r) => (
            <option key={r.harness + r.id} value={r.id}>{`${short(r.title, 40)}${r.local ? "" : " (another harness)"}${r.kind === "headless" ? " · no terminal" : ""}`}</option>
          ))}
        </select>
      ) : (
        <b className="rc-bar-name" data-testid="roles-live-title">{here ? short(here.title, 48) : "no session"}</b>
      )}
      <span className="mono muted rc-bar-count" data-testid="roles-live-count">{agents} agent{agents === 1 ? "" : "s"} · {live} live</span>
      <span className="spacer" />
      <span className="segmented" role="group" aria-label="Density">
        {(["spread", "compact"] as Density[]).map((d) => (
          <button key={d} className={density === d ? "on" : ""} aria-pressed={density === d} onClick={() => setDensity(d)} data-testid={`roles-live-${d}`}>{d}</button>
        ))}
      </span>
      <Button size="sm" variant="ghost" onClick={fit} title="Fit the tree to the page (F)" data-testid="roles-live-fit">Fit</Button>
      <span className="segmented rc-zoom" role="group" aria-label="Zoom">
        <button onClick={() => setZoom(Math.max(0.25, zoom / 1.2))} aria-label="Zoom out" data-testid="roles-live-zoom-out">-</button>
        <button onClick={() => setZoom(1)} title="Back to 100%" data-testid="roles-live-zoom">{Math.round(zoom * 100)}%</button>
        <button onClick={() => setZoom(Math.min(2, zoom * 1.2))} aria-label="Zoom in" data-testid="roles-live-zoom-in">+</button>
      </span>
    </div>
  );
}
