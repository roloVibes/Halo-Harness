// One box of Session's Live drawer (3.6.0.2 R10 R14 R15, R18 R43): its face (LitMini.tsx LitFace), where the layout put
// it; hover = the summary card (R43, letter for letter from truth.ts hoverLines: its name; "agent" or "workflow {W}"; its
// model; its state; "Starts when: {When} (from {source})", one row per line feeding it; its children; "Built {t} in this
// session" when the build tagged it), click = the step-in card (R18: on a step row its tagged child, on a block's head
// the running step's, else the box's live rows). No When label is drawn on Session's lines (R44): the When is here.
import type { MouseEvent } from "react";
import { useHover } from "../../lib/hover/useHover";
import { STATE_WORDS } from "../crew/map/LitBits";
import { LitFace, litState, type Lit } from "../crew/map/LitMini";
import type { PlacedDown, RoutedDown } from "../crew/map/layoutDown";
import { whenWords } from "../crew/map/mapTypes";
import { kidText } from "../crew/map/RunRows";
import type { BoxState } from "../crew/map/overlay";
import type { Hit } from "../crew/map/stepInTarget";
import { hoverLines, newTag, stepRow } from "../crew/map/truth";

const BLOCK_ST: Record<string, BoxState> = { running: "working", done: "done", failed: "failed" };

/** `built`: when a build in this session wrote this box (R29: tagged "new {t}", `data-new`); a drawing `L.unlit` (Just
 *  built, R30) has no `data-lit`. */
type Props = { b: PlacedDown; L: Lit; sid: string; lines: RoutedDown[]; built?: number | null; pick: (h: Hit) => void };

/** R43's lines for box `b`. */
function lines(b: PlacedDown, L: Lit, feeding: RoutedDown[], built: number | null): string[] {
  const blk = b.block ? L.ov?.blocks[b.block.workflow] : undefined;
  const st = blk ? BLOCK_ST[blk.state] || "idle" : litState(b, L.ov).st; // a block: the workflow's own state
  const ob = L.ov?.boxes[b.id];
  const main = b.main ? L.agents.find((a) => a.id === "main") : undefined;
  const model = b.main ? main?.model || "" : (ob?.models || []).join(", ") || String(L.detail?.boxes[b.id]?.facts?.[0]?.model || "");
  const steps = b.block ? (blk?.steps.length ? blk.steps : b.block.steps) : [];
  const children = b.block ? steps.map((s) => stepRow(s.n, s.step, s.agent, s.model, s.state)) : (L.ov?.kids[b.id] || []).map(kidText);
  const [first, ...more] = feeding;
  return hoverLines({ name: b.name, workflow: b.block?.workflow || null, model, state: STATE_WORDS[st], when: first ? whenWords(first.when) : "",
    source: first?.from || "", more: more.map((l) => [whenWords(l.when), l.from]), children, built });
}

export function DownBox({ b, L, sid, lines: all, built = null, pick }: Props) {
  const { st, helper } = litState(b, L.ov);
  const hv = useHover("map", `${sid}:${b.id}`, () => (
    <div className="mp-hover" data-testid="session-map-hover">
      {lines(b, L, all.filter((l) => l.to === b.id), built).map((x, i) => (
        <div key={i} className={i ? "mp-hover-line" : "hc-title"} data-testid="session-map-hover-line">{x}</div>
      ))}
    </div>
  ), !!sid);
  const loose = !!b.block?.under; // R14: a workflow on no box of the map: its block on a full-width row
  const click = (e: MouseEvent<HTMLDivElement>) => {
    const el = e.target as HTMLElement;
    if (el.closest("button, a, input, textarea")) return;
    const row = el.closest<HTMLElement>("[data-testid=session-map-step]");
    if (b.block && row) return pick({ kind: "step", workflow: b.block.workflow, n: Number(row.dataset.n), text: row.textContent || "" });
    const face = e.currentTarget.querySelector<HTMLElement>(b.block ? "[data-testid=session-map-block-head]" : ".mp-lit-row");
    if (b.block) return pick({ kind: "head", workflow: b.block.workflow, text: face?.textContent || "" });
    pick({ kind: "box", box: b.id, name: b.name, text: face?.textContent || STATE_WORDS[st] });
  };
  return (
    <div className={loose ? "mp-box mp-block-box" : "mp-box"} data-lit={L.unlit ? undefined : "live"} data-state={st} data-helper={helper} data-kind={b.kind}
         data-new={b.isNew || built ? "" : undefined} data-workflow={b.block?.workflow}
         data-testid={loose ? "session-map-block" : "session-lit-box"} data-box={b.id} title={!b.block && hv.titles ? `${b.name}: ${STATE_WORDS[st]}` : undefined}
         style={{ position: "absolute", left: b.x, top: b.y, width: b.w, height: b.h }} {...hv.props} onClick={click}>
      <LitFace b={b} ov={L.ov} sid={sid} tag={built ? newTag(built) : undefined} />
    </div>
  );
}
