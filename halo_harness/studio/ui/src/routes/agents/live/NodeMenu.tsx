// A node's "..." menu on Agents -> Live and Session's Map (3.3.16.0 R2: the Fleet Map's NodeMenu, moved here with the
// one tree that draws agents now): Steer, Pause / Resume, Pin its stream, Stop..., Take over..., Hand to..., Record;
// a session's also Shut the session down...; Open in Session for this harness's, Open in Agents: Runs for an
// Orchestra worker's. Each item runs the fleet action it always ran (routes/fleet/actions.ts, extras.ts).
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../../../lib/ui";
import { studio } from "../../../lib/store";
import { hideHover } from "../../../lib/hover/store";
import { openSession } from "../../session/store";
import { askShutdown, askStop, openAgentPanel, pin, select, togglePause } from "../../fleet/actions";
import { askHandoff, record } from "../../fleet/extras";
import { focusSteer } from "../../fleet/Steer";
import { openWorkerRun } from "../run/door";
import { useFleet } from "../../fleet/store";

export type MenuAt = { x: number; y: number; key: string; session?: boolean };

/** Where the menu sits: under the click, kept inside the window by its drawn size (eight items are taller than the
 * room under a node low on the canvas: it opens upward then, so its last item is never cut off). */
function useFitted(box: { current: HTMLDivElement | null }, at: MenuAt): { left: number; top: number } {
  const [pos, setPos] = useState({ left: Math.min(at.x, window.innerWidth - 240), top: at.y + 6 });
  useLayoutEffect(() => { // after every draw (its rows can change while it is open); a state change only when it moves
    const el = box.current;
    if (!el) return;
    const h = el.offsetHeight, w = el.offsetWidth;
    const top = at.y + 6 + h <= window.innerHeight - 8 ? at.y + 6 : Math.max(8, Math.min(at.y - 6, window.innerHeight - 8) - h);
    const left = Math.max(8, Math.min(at.x, window.innerWidth - w - 8));
    if (left !== pos.left || top !== pos.top) setPos({ left, top });
  });
  return pos;
}

export function NodeMenu({ at, onClose }: { at: MenuAt; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const harnesses = useFleet((s) => s.harnesses);
  const pos = useFitted(box, at);
  useEffect(() => {
    hideHover(); // 3.3.16.1: the box's hover card goes while its menu is open
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
  const paused = s.agents?.find((a) => at.key.endsWith("|" + a.agent_id))?.state === "paused";
  const items: [string, string, string, () => void][] = [
    ["steer", "Steer this agent", "send", () => (select(at.key), openAgentPanel(), focusSteer("agent"))],
    ["pause", paused ? "Resume" : "Pause at its next step", paused ? "play" : "pause", () => void togglePause(at.key)],
    ["pin", "Pin its stream (mini stream)", "pin", () => pin(at.key)],
    ["stop", "Stop...", "stop", () => askStop(at.key)],
    ["takeover", "Take over...", "send", () => askHandoff("take_over", at.key)],
    ["handto", "Hand to...", "link", () => askHandoff("hand_to", at.key)],
    ["record", at.session ? "Record the session" : "Record this agent", "file", () => void record(at.key, !at.session)],
  ];
  if (at.session) items.push(["shutdown", "Shut the session down...", "close", () => askShutdown(h, sid)]);
  if (harnesses.find((x) => x.id === h)?.local && studio.get().section !== "session")
    items.push(["session", "Open in Session", "grid", () => openSession(at.session ? { session: sid } : { key: at.key })]);
  if (s.kind === "orchestra-worker") items.push(["orchestra", "Open its run (its lane on Live)", "grid", () => openWorkerRun(String(s.cwd || ""))]); // 3.4.0.0 D
  return createPortal(
    <div ref={box} className="menu glass panel-menu fm-menu" role="menu" style={{ left: pos.left, top: pos.top, width: 228 }} data-testid="fleet-node-menu">
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
