// Agents -> Live's bar (3.3.11.0 R2 as Roles Live's; 3.3.16.0 R2: its own file): Plan | Live, the session picker (this
// harness's sessions, the newest first); the counts, 3.4.0.0 D Run a goal (this halo), History, the
// density, Fit and the zoom. Nothing on it opens anything on its own.
import type { ReactNode } from "react";
import { Button } from "../../../lib/ui";
import type { RecordRef } from "../../../lib/work/record";
import { short } from "../../orchestra/format";
import { PlanLive } from "../../roles/CanvasBar";
import type { Density } from "../../roles/liveLayout";
import { roles, useRoles } from "../../roles/store";
import { HistoryButton } from "./History"; // 3.3.18.0: the past, newest first, each a replay
import { PlanToggle } from "./PlanToggle"; // 3.3.18.0 part 2: the lineup's blocks under the agents
import { RunGoalButton } from "../run/GoalDrawer"; // 3.4.0.0 D: the goal form as a panel (Runs' Start screen went)

type BarProps = { refs: RecordRef[]; sid: string; agents: number; live: number; zoom: number; setZoom: (z: number) => void; fit: () => void;
  empty?: boolean; plan?: { available: boolean; on: boolean; lineup: string }; levels?: ReactNode }; // 3.3.18.0: empty; part 2; part 4

export function LiveBar({ refs, sid, agents, live, zoom, setZoom, fit, empty = false, plan, levels }: BarProps) {
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
        <b className="rc-bar-name" data-testid="roles-live-title">{empty ? "nothing running" : here ? short(here.title, 48) : "no session"}</b>
      )}
      {!empty && <span className="mono muted rc-bar-count" data-testid="roles-live-count">{agents} agent{agents === 1 ? "" : "s"} · {live} live</span>}
      {plan?.available && <PlanToggle on={plan.on} lineup={plan.lineup} />}
      <RunGoalButton />
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
