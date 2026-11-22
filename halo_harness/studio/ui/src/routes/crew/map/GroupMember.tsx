// One member of one of Auto's groups (3.6.0.5 B10 B11 B13): a box at least 48 px tall, `groupBox(w).member` wide, its
// 3 px left edge in its state's colour (working --accent, waiting --warn, done --ok, failed --bad; the group's colour never
// changes with state), "{who}: {description}" over "{model} · {state}" and, for a child of a child, "started by {who}:
// {task}"; every word wraps and the box grows (no cap, no ellipsis). Hover: G4 (with "Why this model: ..."); a click: the
// step-in card on it (stepInTarget.ts, the same why line). [Save as an agent] only on a member no saved agent is.
// 3.6.0.13 L2a L2b: under those lines, what it does NOW in words (nowLine.ts; `data-now` its colour, live-now.css), in
// rows held from the first draw (nowRoom.ts: two, one growth when the drawing is not held, else "a tool · {s}"); the
// state line holds the rows of its longest words too, so the member keeps its height but for NOW's one growth.
import { useContext, useRef, type MouseEvent } from "react";
import { useHover } from "../../../lib/hover/useHover";
import { g4Lines, memberLine, memberState, thirdLine } from "./groupWords";
import { saveAsAgent } from "./LitBits";
import { nowWords } from "./nowLine";
import { heldRows, nowFit, stateRows, type Kept } from "./nowRoom";
import { RunCtx, useNowOf } from "./runParts";
import type { AutoGroup, Member } from "./overlayGroups";
import type { Hit } from "./stepInTarget";

type Props = { g: AutoGroup; m: Member; sid: string; width: number; now: number; pick: (h: Hit) => void; sel: boolean; hidden?: boolean };

export function GroupMember({ g, m, sid, width, now, pick, sel, hidden }: Props) {
  const text = width - 20; // its border (1, left 3) and padding (8 + 8): styles/map-down.css .mp-member
  const nw = useNowOf(m.aid, m.raw, m.started, m.ended);
  const kept = useRef<Kept>({ rows: heldRows(text), grown: false }); // kept for the helper's life, never shrinks
  const fit = nowFit(nw, text, kept.current, !!useContext(RunCtx)?.held);
  kept.current = fit.kept;
  const hv = useHover("map", `${sid}:${m.aid}`, () => (
    <div className="mp-hover" data-testid="session-map-hover">
      {g4Lines(m, now, nowWords(nw)).map((x, i) => (
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
    <div className="mp-member" data-member={m.aid} data-state={m.state} data-raw={m.raw} data-selected={sel ? "" : undefined} hidden={hidden}
         style={{ width }} {...hv.props} onClick={click} title={hv.titles ? `${memberLine(m)}: ${memberState(m)}` : undefined}>
      <span className="mp-member-line" data-testid="map-member-line">{memberLine(m)}</span>
      <span className="mp-member-state mono" data-testid="map-member-state" style={{ minHeight: stateRows(m.model, text) * 17 }}>{memberState(m)}</span>
      {third && <span className="mp-member-by" data-testid="map-member-by">{third}</span>}
      <span className="mp-member-now mono" data-testid="map-member-now" data-now={nw.kind} style={{ minHeight: fit.rows * 17 }}>
        {fit.text}{fit.secs && <span className="mp-clock-secs">{fit.secs}</span>}
      </span>
      {m.made && sid && (
        <button type="button" className="mp-link" data-testid="map-save-agent" title="Open the Agents form with an agent built from this helper; nothing is saved until you press Save there"
                onClick={(e) => { e.stopPropagation(); void saveAsAgent(sid, m.aid); }}>
          Save as an agent
        </button>
      )}
    </div>
  );
}
