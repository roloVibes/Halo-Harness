// Agents -> Live's bar (3.3.11.0 R2 as Roles Live's; 3.3.16.0 R2 "the Fleet fold": its own file): Plan | Live, the
// scope switch **this halo | fleet** (`F` on the canvas), then on this halo the session picker (this harness's sessions,
// the newest first) and on the fleet the machines' line; the counts, 3.4.0.0 D Run a goal (this halo), History, the
// density, Fit and the zoom. Nothing on it opens anything on its own.
import type { ReactNode } from "react";
import { Button } from "../../../lib/ui";
import type { RecordRef } from "../../../lib/work/record";
import { short } from "../../orchestra/format";
import { PlanLive } from "../../roles/CanvasBar";
import type { Density } from "../../roles/liveLayout";
import { roles, useRoles } from "../../roles/store";
import { useFleetPack } from "../../fleet/store";
import { setScope, useLiveScope } from "./scope";
import { HistoryButton } from "./History"; // 3.3.18.0: the past, newest first, each a replay
import { PlanToggle } from "./PlanToggle"; // 3.3.18.0 part 2: the lineup's blocks under the agents
import { RunGoalButton } from "../run/GoalDrawer"; // 3.4.0.0 D: the goal form as a panel (Runs' Start screen went)

export function ScopeSwitch() {
  const scope = useLiveScope();
  const pack = useFleetPack(); // 3.4.0.0 C: the fleet scope is the fleet pack's door
  if (!pack) return null;
  return (
    <span className="segmented rlm-scope" role="group" aria-label="What Live draws: this halo or the whole fleet" data-testid="live-scope" data-scope={scope}>
      {(["here", "fleet"] as const).map((s) => (
        <button key={s} className={scope === s ? "on" : ""} aria-pressed={scope === s} onClick={() => setScope(s)} data-testid={`live-scope-${s}`}
                title={s === "here" ? "This halo: one session's agents (F on the canvas switches)" : "Fleet: every machine, its sessions and their agents (F on the canvas switches)"}>
          {s === "here" ? "this halo" : "fleet"}
        </button>
      ))}
    </span>
  );
}

type BarProps = { refs: RecordRef[]; sid: string; agents: number; live: number; machines: number; zoom: number; setZoom: (z: number) => void; fit: () => void;
  empty?: boolean; plan?: { available: boolean; on: boolean; lineup: string }; levels?: ReactNode }; // 3.3.18.0: empty; part 2; part 4

export function LiveBar({ refs, sid, agents, live, machines, zoom, setZoom, fit, empty = false, plan, levels }: BarProps) {
  const density = useRoles((s) => s.liveDensity);
  const setDensity = (d: Density) => roles.update(() => ({ liveDensity: d }));
  const scope = useLiveScope();
  const here = refs.find((r) => r.id === sid);
  return (
    <div className="rc-bar rlm-bar">
      <PlanLive />
      <ScopeSwitch />
      {scope === "fleet" ? (
        <b className="rc-bar-name" data-testid="roles-live-title">{machines} machine{machines === 1 ? "" : "s"}</b>
      ) : refs.length > 1 ? (
        <select className="input mono rlm-pick-session" value={sid} onChange={(e) => roles.update(() => ({ liveSid: e.target.value }))}
                aria-label="The session Live draws" data-testid="roles-live-session">
          {refs.map((r) => (
            <option key={r.harness + r.id} value={r.id}>{`${short(r.title, 40)}${r.local ? "" : " (another harness)"}${r.kind === "headless" ? " · no terminal" : ""}`}</option>
          ))}
        </select>
      ) : (
        <b className="rc-bar-name" data-testid="roles-live-title">{empty ? "nothing running" : here ? short(here.title, 48) : "no session"}</b>
      )}
      {!empty && <span className="mono muted rc-bar-count" data-testid="roles-live-count">{agents} agent{agents === 1 ? "" : "s"} · {live} live</span>}
      {plan?.available && scope === "here" && <PlanToggle on={plan.on} lineup={plan.lineup} />}
      {scope === "here" && <RunGoalButton />}
      <HistoryButton />
      <span className="spacer" />
      <span className="segmented" role="group" aria-label="Density">
        {(["spread", "compact"] as Density[]).map((d) => (
          <button key={d} className={density === d ? "on" : ""} aria-pressed={density === d} onClick={() => setDensity(d)} data-testid={`roles-live-${d}`}>{d}</button>
        ))}
      </span>
      {!empty && levels}
      <Button size="sm" variant="ghost" onClick={fit} title="Fit the tree to the page (f): the level that shows all of it readably" data-testid="roles-live-fit">Fit</Button>
      <span className="segmented rc-zoom" role="group" aria-label="Zoom">
        <button onClick={() => setZoom(Math.max(0.12, zoom / 1.2))} aria-label="Zoom out" data-testid="roles-live-zoom-out">-</button>
        <button onClick={() => setZoom(1)} title="Back to 100%" data-testid="roles-live-zoom">{Math.round(zoom * 100)}%</button>
        <button onClick={() => setZoom(Math.min(2, zoom * 1.2))} aria-label="Zoom in" data-testid="roles-live-zoom-in">+</button>
      </span>
    </div>
  );
}
