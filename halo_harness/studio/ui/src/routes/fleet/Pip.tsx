// The picture-in-picture mini stream: the pinned agent (Space, or Pin) keeps
// a small floating panel over whatever you look at -- the Roles canvas, an
// Orchestra run, another agent -- with its state, cost, what it does now and
// the newest lines of its stream, typing as they arrive. It hides while the
// Fleet agent panel already shows that agent; drag it by its bar, Open goes
// to it in Fleet, Esc (or x) unpins it.
import { useMemo, useRef, useState, type PointerEvent } from "react";
import { Icon, toolIcon } from "../../lib/ui";
import { goSection, studio, useStore } from "../../lib/store";
import { layoutStore } from "../../lib/workspace/persist";
import { cost, short } from "../orchestra/format";
import { openAgentPanel, pin, select } from "./actions";
import { nowText } from "./MapNode";
import { EMPTY } from "./streams";
import { Typed } from "./StreamViews";
import { agentMotion, enterWorkspace, findAgent, isLive, showsStart, useFleet, type FleetState } from "./store";

const LINES = 8;

export function FleetPip() {
  const pinned = useFleet((s) => s.pinned);
  const selected = useFleet((s) => s.selected);
  const harnesses = useFleet((s) => s.harnesses);
  const start = useFleet(showsStart);
  const st = useFleet((s) => (s.pinned ? s.streams[s.pinned] : undefined)) || EMPTY;
  const doneAt = useFleet((s) => s.doneAt[s.pinned] || 0);
  const section = useStore(studio, (s) => s.section);
  const panelShown = useStore(layoutStore("fleet"), (l) => !!l.layout?.["fleet-agent"] && !l.layout["fleet-agent"].collapsed);
  const [off, setOff] = useState({ x: 0, y: 0 });
  const drag = useRef<{ sx: number; sy: number; x: number; y: number } | null>(null);
  const ref = useMemo(() => (pinned ? findAgent({ harnesses } as FleetState, pinned) : null), [pinned, harnesses]);
  if (!pinned || !ref) return null;
  if (section === "fleet" && !start && panelShown && selected === pinned) return null;
  const { a } = ref;
  const lines = st.entries.filter((e) => e.kind === "text" || e.kind === "thinking" || e.kind === "tool_call" || e.kind === "spawn" || e.kind === "user").slice(-LINES);
  const down = (e: PointerEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).closest("button")) return;
    drag.current = { sx: e.clientX, sy: e.clientY, x: off.x, y: off.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (d) setOff({ x: d.x + e.clientX - d.sx, y: d.y + e.clientY - d.sy });
  };
  const goTo = () => {
    goSection("fleet");
    enterWorkspace();
    select(pinned);
    window.setTimeout(() => openAgentPanel(), 80);
  };
  return (
    <aside className="fleet-pip glass" data-testid="fleet-pip" data-motion={agentMotion(a, doneAt)} style={{ transform: `translate(${off.x}px, ${off.y}px)` }} aria-label={`Mini stream: ${a.name || a.agent_id}`}>
      <span className="hud-brackets" aria-hidden="true" />
      <header className="pip-bar" onPointerDown={down} onPointerMove={move} onPointerUp={() => (drag.current = null)} title="Drag to move it">
        <span className="panel-dot" data-motion={agentMotion(a, doneAt)} aria-hidden="true" />
        <b className="pip-name">{a.name || a.agent_id}</b>
        <span className="mono muted pip-meta">{a.state} · {cost(a.cost_usd)} · {short(ref.h.name || "", 16)}</span>
        <button className="icon-btn" onClick={goTo} title="Open it in Fleet" aria-label="Open it in Fleet">
          <Icon name="popout" />
        </button>
        <button className="icon-btn" onClick={() => pin("")} title="Unpin (Esc)" aria-label="Unpin">
          <Icon name="close" />
        </button>
      </header>
      <div className="pip-now mono">{short(nowText(a), 90)}</div>
      <div className="pip-body">
        {lines.map((e, i) =>
          e.kind === "tool_call" || e.kind === "spawn" ? (
            <div key={i} className="pip-tool mono">
              <Icon name={e.kind === "spawn" ? "agent" : toolIcon(String(e.name || "")) || "pulse"} size={12} /> {short(e.label || `${e.name}: ${e.task || ""}`, 70)}
            </div>
          ) : (
            <div key={i} className="pip-text" data-kind={e.kind} data-you={e.you || undefined}>
              {e.kind === "user" ? <span className="mono muted">{e.you ? "you: " : "asked: "}</span> : null}
              {i === lines.length - 1 && e.kind !== "user" ? <Typed text={short(e.text || "", 400)} live={isLive(a)} /> : short(e.text || "", 220)}
            </div>
          ),
        )}
        {!lines.length && <div className="muted">Its stream shows here as it works.</div>}
      </div>
    </aside>
  );
}
