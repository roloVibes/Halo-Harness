// One of Auto's groups as drawn in Session's Live drawer and in Agents -> Live (3.6.0.5 B7 B9 B10 B11 B13, R14 on Auto):
// a border-box in its own colour (`--group-{colour}`, a 2 px border, 10 px padding, radius 8, fill 10 %, 5 % once all its
// members are done), never in a state's colour. Its head is measured and wraps (nothing cut): the name (13.5 px, 600; a
// workflow run's R14 head while it runs), the counts line ("{f} failed" in --bad) or the all-done line, the why line
// (`whyOf`, only when a member has a pick's reason). Then a workflow run's steps as R14's rows (only when its step runner
// gave it steps), else its members in start order, up to 8, then "+{n} more" (its hover lists every one). Hover the head:
// G3; a click on it: the group's card (a row per live member). 3.6.0.13 L4: the counts read the raw state, "{v} waiting
// on you" in --warn, and "all done" only when every member is raw done (R1). `data-pad` tells useMeasure (runFrame.ts) its padding and
// border. Nothing here fetches, times or calls the network (tests/test_map_groups.py guards it). 3.6.0.15 L8: an all-done
// group folds to its head (foldRule.ts; `data-folded`): its rows are hidden, its members stay mounted, never while held.
import { useContext, useRef, type MouseEvent } from "react";
import { useHover } from "../../../lib/hover/useHover";
import { foldNext } from "./foldRule";
import type { PlacedDown } from "./layoutDown";
import type { Lit } from "./LitMini";
import { groupBox } from "./litView";
import { countParts, doneLine, g3Lines, isAllDone, memberLine, memberState, moreMembers, SHOWN_MEMBERS, whyLine } from "./groupWords";
import { GroupMember } from "./GroupMember";
import { runningStep } from "./overlayBlocks";
import type { AutoGroup } from "./overlayGroups";
import { RunCtx } from "./runParts";
import type { Hit } from "./stepInTarget";
import { blockHead, stepRow } from "./truthBits";

type Props = { b: PlacedDown; L: Lit; sid: string; pick: (h: Hit) => void; live?: boolean; sel?: boolean; card?: string };

/** The group's own state, for tests only (its colour never follows it). */
function stateOf(g: AutoGroup): string {
  const s = g.members.map((m) => m.state);
  return s.includes("waiting") ? "waiting" : s.includes("working") ? "working" : !s.length ? "idle"
    : s.every((x) => x === "done") ? "done" : s.includes("failed") ? "failed" : "done";
}

function Head({ g, name }: { g: AutoGroup; name: string }) {
  const why = whyLine(g);
  return (
    <>
      <b className="mp-group-name" data-testid="map-group-name">{name}</b>
      <span className="mp-group-counts mono" data-testid="map-group-counts">
        {isAllDone(g) ? doneLine(g) : countParts(g).map((p, i) => (
          <span key={i}>{i ? " · " : ""}{p.bad || p.warn ? <span className={p.bad ? "mp-bad" : "mp-warn"}>{p.text}</span> : p.text}</span>
        ))}
      </span>
      {why && <span className="mp-group-why" data-testid="map-group-why">{why}</span>}
    </>
  );
}

export function GroupBlock({ b, L, sid, pick, live, sel, card }: Props) {
  // 3.6.0.13 L7a (R12): the members the box was laid out with (its held geometry's), in their state now; one that joined
  // while the drawing is held is drawn when it is laid out again, never over the box's held height
  const fresh = L.groups?.find((x) => x.n === b.group?.n), drawn = b.group?.members;
  const g = fresh && drawn ? { ...fresh, members: fresh.members.filter((m) => drawn.includes(m.aid)) } : fresh;
  const hv = useHover("map", `${sid}:${b.id}`, () => (
    <div className="mp-hover" data-testid="session-map-hover">
      {(g ? g3Lines(g) : []).map((x, i) => (
        <div key={i} className={i ? "mp-hover-line" : "hc-title"} data-testid="session-map-hover-line">{x}</div>
      ))}
    </div>
  ), !!sid && !!g);
  const held = !!useContext(RunCtx)?.held, fold = useRef<boolean | undefined>(undefined);
  const folded = g ? (fold.current = foldNext(fold.current, g, L.now || 0, held)) : false;
  if (!g || !b.group) return null;
  const lit = g.workflow ? L.ov?.blocks[g.workflow] : undefined;
  const at = g.steps && lit ? runningStep({ state: lit.state, steps: g.steps }) : undefined;
  const name = g.steps && g.workflow ? blockHead(g.workflow, at, at ? g.steps.length : undefined) : g.name;
  const box = groupBox(b.w);
  const more = g.members.length - SHOWN_MEMBERS;
  const head = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("button, a, input, textarea")) return;
    pick({ kind: "group", n: g.n, text: e.currentTarget.querySelector("[data-testid=map-group-counts]")?.textContent || "" });
  };
  const step = (e: MouseEvent<HTMLElement>, n: number) => {
    e.stopPropagation();
    if (g.workflow) pick({ kind: "step", workflow: g.workflow, n, text: e.currentTarget.textContent || "" });
  };
  return (
    <div className="mp-group" data-testid={live ? "live-group" : "session-map-group"} data-box={b.id} data-map-box={live ? b.id : undefined}
         data-pad="24" data-group={g.n} data-colour={b.group.colour} data-state={stateOf(g)} data-done={isAllDone(g) ? "" : undefined}
         data-folded={folded ? "" : undefined} data-workflow={g.workflow} data-selected={sel ? "" : undefined} tabIndex={0}
         style={{ position: "absolute", left: b.x, top: b.y, width: b.w, height: b.h }}
         onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) (e.preventDefault(), pick({ kind: "group", n: g.n, text: "" })); }}>
      <div className="mp-inner">
        <div className="mp-group-head" data-testid="map-group-head" {...hv.props} onClick={head}>
          <Head g={g} name={name} />
        </div>
        {g.steps ? (
          <div className="mp-group-steps" hidden={folded}>
            {g.steps.map((s) => (
              <span key={s.n} className="mp-step mono" data-testid="session-map-step" data-n={s.n} data-state={s.state} onClick={(e) => step(e, s.n)}>
                {stepRow(s.n, s.step, s.agent, s.model, s.state)}
              </span>
            ))}
          </div>
        ) : (
          <div className="mp-group-members" data-per={box.per} hidden={folded}>
            {g.members.map((m, i) => (
              <GroupMember key={m.aid} g={g} m={m} sid={sid} width={box.member} now={L.now || 0} pick={pick}
                           sel={card === `member:${m.aid}`} hidden={more > 0 && i >= SHOWN_MEMBERS} />
            ))}
            {more > 0 && (
              <span className="mp-group-more mono" data-testid="map-group-more" title={g.members.map((m) => `${memberLine(m)}: ${memberState(m)}`).join("\n")}>
                {moreMembers(more)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
