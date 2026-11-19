// One member of one of Auto's groups (3.6.0.5 B10 B11 B13): a box at least 48 px tall, `groupBox(w).member` wide, its
// 3 px left edge in its state's colour (working --accent, waiting --warn, done --ok, failed --bad; the group's colour never
// changes with state), "{who}: {description}" over "{model} · {state}" and, for a child of a child, "started by {who}:
// {task}"; every word wraps and the box grows (no cap, no ellipsis). Hover: G4 (with "Why this model: ..."); a click: the
// step-in card on it (stepInTarget.ts, the same why line). [Save as an agent] only on a member no saved agent is.
import type { MouseEvent } from "react";
import { useHover } from "../../../lib/hover/useHover";
import { g4Lines, memberLine, memberState, thirdLine } from "./groupWords";
import { saveAsAgent } from "./LitBits";
import type { AutoGroup, Member } from "./overlayGroups";
import type { Hit } from "./stepInTarget";

type Props = { g: AutoGroup; m: Member; sid: string; width: number; now: number; pick: (h: Hit) => void; sel: boolean; hidden?: boolean };

export function GroupMember({ g, m, sid, width, now, pick, sel, hidden }: Props) {
  const hv = useHover("map", `${sid}:${m.aid}`, () => (
    <div className="mp-hover" data-testid="session-map-hover">
      {g4Lines(m, now).map((x, i) => (
        <div key={i} className={i ? "mp-hover-line" : "hc-title"} data-testid="session-map-hover-line">{x}</div>
      ))}
    </div>
  ), !!sid);
  const third = thirdLine(g, m);
  const click = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("button, a, input, textarea")) return;
    e.stopPropagation();
    pick({ kind: "member", aid: m.aid, text: [memberLine(m), memberState(m)].join(" · ") });
  };
  return (
    <div className="mp-member" data-member={m.aid} data-state={m.state} data-selected={sel ? "" : undefined} hidden={hidden}
         style={{ width }} {...hv.props} onClick={click} title={hv.titles ? `${memberLine(m)}: ${memberState(m)}` : undefined}>
      <span className="mp-member-line" data-testid="map-member-line">{memberLine(m)}</span>
      <span className="mp-member-state mono" data-testid="map-member-state">{memberState(m)}</span>
      {third && <span className="mp-member-by" data-testid="map-member-by">{third}</span>}
      {m.made && sid && (
        <button type="button" className="mp-link" data-testid="map-save-agent" title="Open the Agents form with an agent built from this helper; nothing is saved until you press Save there"
                onClick={(e) => { e.stopPropagation(); void saveAsAgent(sid, m.aid); }}>
          Save as an agent
        </button>
      )}
    </div>
  );
}
