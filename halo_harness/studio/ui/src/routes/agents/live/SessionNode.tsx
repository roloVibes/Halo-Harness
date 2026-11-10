// A session on the Live tree (3.3.16.0 R2 "the Fleet fold"; the Fleet Map's session card and its Tree panel's session
// row before): its state dot, title and kind chip (no terminal for a headless one), the project and branch with its
// git chips (dirty, ahead / behind, worktree, from GET fleet/conflicts' rooms), the cost counting up, a `!` chip
// naming the file when another session edits it too, a `mission` chip on a mission part's session, and its "..." menu
// (the session's: Record the session, Shut it down...). A click selects its main agent; in Session's Map the chosen
// session is marked (`data-chosen`).
import type { KeyboardEvent, MouseEvent } from "react";
import { cost, short } from "../../orchestra/format";
import { usePanels } from "../../fleet/pstore";
import { sessionMotion, useFleet } from "../../fleet/store";
import type { LiveBox } from "../../roles/liveLayout";
import type { MenuAt } from "./NodeMenu";
import { projectLabel, useTicker } from "./nodeBits";

function GitChips({ hid, sid, dirty }: { hid: string; sid: string; dirty: boolean | undefined }) {
  const room = usePanels((st) => st.conflicts?.rooms.flatMap((r) => r.cards).find((x) => x.harness === hid && x.session_id === sid));
  const d = room?.dirty ?? dirty;
  const chips: [string, string][] = [["dirty", d ? "dirty" : "clean"]];
  if (room?.ahead) chips.push(["ahead", `ahead ${room.ahead}`]);
  if (room?.behind) chips.push(["behind", `behind ${room.behind}`]);
  if (room?.worktree) chips.push(["worktree", `worktree ${room.worktree.replace(/[\\/]+$/, "").split(/[\\/]/).pop()}`]);
  return (
    <span className="rlm-git" data-testid="fleet-git-chips">
      {chips.map(([k, label]) => <span key={k} className="og-chip mono" data-git={k} data-on={k === "dirty" ? d || undefined : true}>{label}</span>)}
    </span>
  );
}

type Props = { b: LiveBox; selected: boolean; onPick: (key: string) => void; onMenu: (m: MenuAt) => void };

export function SessionNode({ b, selected, onPick, onMenu }: Props) {
  const n = b.node;
  const hid = n.harness || "";
  const sid = n.sid || "";
  const s = useFleet((st) => st.harnesses.find((h) => h.id === hid)?.sessions.find((x) => x.session_id === sid));
  const chosen = useFleet((st) => !!st.scope.harness && st.scope.session === sid);
  const clash = usePanels((st) => st.conflicts?.conflicts.find((x) => [x.a, x.b].some((r) => r.harness === hid && r.session_id === sid)));
  const shown = useTicker(Number(n.cost) || 0);
  if (!s) return null;
  const pick = () => onPick(n.key);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), pick());
  const menu = (e: MouseEvent) => (e.stopPropagation(), onMenu({ x: e.clientX, y: e.clientY, key: n.key, session: true }));
  return (
    <div className="rlm-node rlm-session" style={{ left: b.x, top: b.y, width: b.w, height: b.h }} role="button" tabIndex={0} onClick={pick} onKeyDown={onKey}
         data-testid="fleet-session" data-sid={sid} data-harness={hid} data-status={s.status || "unknown"} data-motion={sessionMotion(s)}
         data-chosen={chosen || undefined} data-selected={selected || undefined} aria-label={`session ${n.name}`}
         title={`${n.name}\n${s.cwd || ""}\n${s.kind || "session"} · ${s.status || ""}`}>
      <div className="rlm-head">
        <span className="rlm-dot" aria-hidden="true" />
        <b className="rlm-name">{short(n.name, 24)}</b>
        <span className="spacer" />
        {s.mission && <span className="og-chip mono" data-testid="fleet-tree-mission" title={`mission ${s.mission}, part ${s.part ?? "?"}`}>mission</span>}
        <span className="og-chip mono rlm-role">{n.role}</span>
        <button className="rlm-more" onClick={menu} aria-label="session: more" title="Record, shut down..." data-testid="fleet-session-more">...</button>
      </div>
      <div className="mono muted rlm-line">
        {short(projectLabel(s), 30)} · <span data-testid="fleet-session-cost">{cost(shown)}</span>
        {clash && (
          <span className="og-chip mono rlm-clash" data-testid="fleet-conflict-chip" title={`${clash.a.name} and ${clash.b.name} are both editing ${clash.file}`}>
            {"! " + short(clash.file.split("/").pop(), 12)}
          </span>
        )}
      </div>
      <GitChips hid={hid} sid={sid} dirty={!!s.project?.dirty} />
    </div>
  );
}
