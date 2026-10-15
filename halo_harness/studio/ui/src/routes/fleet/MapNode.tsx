// The fleet map's pieces, drawn in SVG: an agent node (state dot and motion,
// name and role, what it does now, the model pill, the tool icon while a
// tool runs, a cost ticker that counts up, a `...` button) and a session
// card (status dot, title, kind chip, project + branch, cost, `...`). The
// `...` opens NodeMenu: Steer, Pause / Resume, Pin, Stop, Take over, Hand
// to..., Record, Shutdown and Record (a session), Open in Orchestra / Flow.
// R4: a card in conflict carries a warning chip with the file; By project a
// card's third line has its git chips (dirty, ahead / behind, worktree).
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { Icon, toolIcon } from "../../lib/ui";
import { goSection } from "../../lib/store";
import { cost, short } from "../orchestra/format";
import { askShutdown, askStop, openAgentPanel, pin, select, togglePause } from "./actions";
import { askHandoff, record } from "./extras";
import { usePanels } from "./pstore";
import { projectLabel, type Card, type NodeBox } from "./layout";
import { agentMotion, fleet, keyOf, sessionMotion, sessionTitle, toolOf, useFleet } from "./store";
import type { AgentRow } from "./types";

/** A number that counts up to `value` over ~600 ms (the cost ticker). */
export function useTicker(value: number): number {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    if (value <= a) {
      from.current = value;
      setShown(value);
      return;
    }
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / 600);
      const v = a + (value - a) * k;
      setShown(v);
      if (k < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return shown;
}

const fit = (text: string, px: number) => short(text, Math.max(4, Math.floor(px / 6.4)));

export function nowText(a: AgentRow): string {
  if (a.state === "waiting") return "waits on you";
  if (a.state === "paused") return "paused: holds at its next step";
  if (a.state === "queued") return "queued";
  if (a.current) return a.current;
  if (a.state === "done" || a.state === "failed" || a.state === "stopped") return `${a.state}${a.last_text ? ": " + a.last_text : ""}`;
  return a.task || "";
}

type MenuAt = { x: number; y: number; key: string; session?: boolean };
const menuOf = (e: MouseEvent, key: string, session = false): MenuAt => ({ x: e.clientX, y: e.clientY, key, session });

export function AgentNode({ n, onMenu }: { n: NodeBox; onMenu: (m: MenuAt) => void }) {
  const { key, a } = n.ref;
  const selected = useFleet((s) => s.selected === key);
  const pinned = useFleet((s) => s.pinned === key);
  const doneAt = useFleet((s) => s.doneAt[key] || 0);
  const act = useFleet((s) => s.activity[key]);
  const tool = a.state === "running" ? toolOf(a, act) : "";
  const shownCost = useTicker(Number(a.cost_usd) || 0);
  const name = a.name || a.role || a.agent_id;
  const role = a.role && a.role !== name ? a.role : a.bio && a.bio !== name ? a.bio : "";
  const right = 128;
  return (
    <g className="fm-node" data-testid="fleet-node" data-key={key} data-state={a.state || "none"} data-motion={agentMotion(a, doneAt)} data-selected={selected || undefined}
       data-hc={n.hc} transform={`translate(${n.x} ${n.y})`} role="button" tabIndex={0} aria-label={`${name}: ${a.state}`}
       onClick={() => select(key)} onDoubleClick={() => openAgentPanel(key)} onKeyDown={(e) => e.key === "Enter" && openAgentPanel(key)}>
      <title>{`${name}${role ? " (" + role + ")" : ""}: ${a.state}${a.task ? "\n" + a.task : ""}`}</title>
      {selected && <rect className="fm-ring" x={-4} y={-4} width={n.w + 8} height={n.h + 8} rx={11} />}
      <rect className="fm-shape" width={n.w} height={n.h} rx={8} />
      <circle className="fm-dot" cx={12} cy={14} r={4} />
      <text className="fm-name" x={22} y={17}>
        {fit(name, n.w - right - 60)}
        {role && <tspan className="fm-role">{" · " + fit(role, 70)}</tspan>}
      </text>
      <text className="fm-now" x={22} y={32}>{fit(nowText(a), n.w - 90)}</text>
      {a.model && (
        <g className="fm-pill" transform={`translate(${n.w - right + 8} 6)`}>
          <rect width={92} height={15} rx={7.5} />
          <text x={46} y={11} textAnchor="middle">{fit(String(a.model).replace(/^[a-z]+:/, "").split("/").pop() || "", 84)}</text>
        </g>
      )}
      {tool && (
        <g className="fm-tool" transform={`translate(${n.w - right - 14} 5)`} data-tool={tool}>
          <title>{a.current || tool}</title>
          <Icon name={toolIcon(tool)} size={14} />
        </g>
      )}
      {pinned && <g className="fm-pin" transform={`translate(${n.w - right - 30} 5)`}><Icon name="pin" size={13} /></g>}
      <text className="fm-cost" x={n.w - 30} y={32} textAnchor="end">{cost(shownCost)}</text>
      <g className="fm-more" transform={`translate(${n.w - 24} 21)`} role="button" aria-label={`${name}: more`}
         onClick={(e) => (e.stopPropagation(), onMenu(menuOf(e, key)))} onDoubleClick={(e) => e.stopPropagation()}>
        <rect width={18} height={14} rx={4} />
        <text x={9} y={10.5} textAnchor="middle">...</text>
      </g>
    </g>
  );
}

function GitChips({ c }: { c: Card }) {
  const s = c.session;
  const room = usePanels((st) => st.conflicts?.rooms.flatMap((r) => r.cards).find((x) => x.harness === c.harness.id && x.session_id === s.session_id));
  const chips: [string, string][] = [];
  const dirty = room?.dirty ?? s.project?.dirty;
  chips.push(["dirty", dirty ? "dirty" : "clean"]);
  if (room?.ahead) chips.push(["ahead", `ahead ${room.ahead}`]);
  if (room?.behind) chips.push(["behind", `behind ${room.behind}`]);
  if (room?.worktree) chips.push(["worktree", `worktree ${room.worktree.replace(/[\\/]+$/, "").split(/[\\/]/).pop()}`]);
  let x = 24;
  return (
    <g className="fm-git" data-testid="fleet-git-chips" transform={`translate(0 ${c.h - 21})`}>
      {chips.map(([k, label]) => {
        const w = label.length * 6 + 12;
        const at = x;
        x += w + 4;
        return (
          <g key={k} className="fm-chip" data-git={k} data-on={k === "dirty" ? dirty || undefined : true} transform={`translate(${at} 0)`}>
            <rect width={w} height={15} rx={7.5} />
            <text x={w / 2} y={11} textAnchor="middle">{label}</text>
          </g>
        );
      })}
    </g>
  );
}

export function SessionCard({ c, onMenu, byProject }: { c: Card; onMenu: (m: MenuAt) => void; byProject?: boolean }) {
  const s = c.session;
  const clash = usePanels((st) => st.conflicts?.conflicts.find((x) => [x.a, x.b].some((r) => r.harness === c.harness.id && r.session_id === s.session_id)));
  const main = keyOf(c.harness.id, s.session_id, (s.agents || []).find((a) => !a.parent)?.agent_id || "main");
  const sessionCost = useTicker(Number(s.cost_usd) || 0);
  return (
    <g className="fm-card" data-testid="fleet-session" data-status={s.status || "unknown"} data-motion={sessionMotion(s)} data-hc={c.hc} transform={`translate(${c.x} ${c.y})`}
       role="button" aria-label={`session ${sessionTitle(s)}`} onClick={() => select(main)} onDoubleClick={() => openAgentPanel(main)}>
      <title>{`${sessionTitle(s)}\n${s.cwd || ""}\n${c.harness.name || ""} · ${s.kind || "session"} · ${s.status || ""}`}</title>
      <rect className="fm-card-shape" width={c.w} height={c.h} rx={9} />
      <rect className="fm-hc" x={0} y={8} width={3} height={c.h - 16} rx={1.5} />
      <circle className="fm-dot" cx={13} cy={16} r={4} />
      <text className="fm-title" x={24} y={20}>{fit(sessionTitle(s), c.w - (clash ? 196 : 120))}</text>
      <g className="fm-chip" transform={`translate(${c.w - 92} 7)`}>
        <rect width={62} height={15} rx={7.5} />
        <text x={31} y={11} textAnchor="middle">{short(s.kind || "session", 10)}</text>
      </g>
      <text className="fm-sub" x={24} y={39}>{fit(projectLabel(s), c.w - 110)}</text>
      <text className="fm-cost" x={c.w - 30} y={39} textAnchor="end">{cost(sessionCost)}</text>
      {clash && (
        <g className="fm-clash" data-testid="fleet-conflict-chip" transform={`translate(${c.w - 166} 7)`}>
          <title>{`${clash.a.name} and ${clash.b.name} are both editing ${clash.file}`}</title>
          <rect width={70} height={15} rx={7.5} />
          <text x={35} y={11} textAnchor="middle">{"! " + short(clash.file.split("/").pop(), 9)}</text>
        </g>
      )}
      {byProject && <GitChips c={c} />}
      <g className="fm-more" transform={`translate(${c.w - 24} 7)`} role="button" aria-label="session: more" onClick={(e) => (e.stopPropagation(), onMenu(menuOf(e, main, true)))}>
        <rect width={18} height={14} rx={4} />
        <text x={9} y={10.5} textAnchor="middle">...</text>
      </g>
    </g>
  );
}

export function NodeMenu({ at, onClose }: { at: MenuAt; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const harnesses = useFleet((s) => s.harnesses);
  useEffect(() => {
    const off = (e: PointerEvent) => !box.current?.contains(e.target as Node) && onClose();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && (e.preventDefault(), onClose());
    window.addEventListener("pointerdown", off, true);
    window.addEventListener("keydown", esc, true);
    box.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus({ preventScroll: true });
    return () => {
      window.removeEventListener("pointerdown", off, true);
      window.removeEventListener("keydown", esc, true);
    };
  }, [onClose]);
  const [h, sid] = at.key.split("|");
  const s = harnesses.find((x) => x.id === h)?.sessions.find((x) => x.session_id === sid);
  if (!s) return null;
  const paused = s?.agents?.find((a) => at.key.endsWith("|" + a.agent_id))?.state === "paused";
  const items: [string, string, string, () => void][] = [
    ["steer", "Steer this agent", "send", () => (select(at.key), openAgentPanel(), fleet.update((st) => ({ steerFocus: st.steerFocus + 1 })))],
    ["pause", paused ? "Resume" : "Pause at its next step", paused ? "play" : "pause", () => void togglePause(at.key)],
    ["pin", "Pin its stream (mini stream)", "pin", () => pin(at.key)],
    ["stop", "Stop...", "stop", () => askStop(at.key)],
    ["takeover", "Take over...", "send", () => askHandoff("take_over", at.key)],
    ["handto", "Hand to...", "link", () => askHandoff("hand_to", at.key)],
    ["record", at.session ? "Record the session" : "Record this agent", "file", () => void record(at.key, !at.session)],
  ];
  if (at.session) items.push(["shutdown", "Shut the session down...", "close", () => askShutdown(h, sid)]);
  if (s?.kind === "orchestra-worker") items.push(["orchestra", "Open in Orchestra", "grid", () => goSection("orchestra")]);
  if (s?.kind === "flow") items.push(["flow", "Open in Flow", "grid", () => goSection("flow")]);
  return createPortal(
    <div ref={box} className="menu glass panel-menu fm-menu" role="menu" style={{ left: Math.min(at.x, window.innerWidth - 240), top: Math.min(at.y + 6, window.innerHeight - 240), width: 228 }} data-testid="fleet-node-menu">
      {items.map(([id, label, icon, run]) => (
        <button key={id} role="menuitem" className="menu-item" data-item={id} onClick={() => (onClose(), run())}>
          <Icon name={icon} />
          <span className="menu-label">{label}</span>
        </button>
      ))}
    </div>,
    document.body,
  );
}

export type { MenuAt };
