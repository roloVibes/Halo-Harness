// A workflow square as a block on the Cast canvas (3.3.16.3, the owner: "here is the media workflow ... all these agents
// you can combine or add, little blocks in there"): a title bar (the chevron, the square's name, its ⋯ menu and its `x`,
// then its purpose -- the DOES line), then, open, one small agent card per bio of its lineup (its role, the model's
// short name, what the model takes), folded, the 3.3.16.0 card's TAKES / GIVES / COSTS lines; a footer with its limits
// and its cost band -- or, with no line from main, "not connected: main never uses it" and a dashed edge. One fact per
// row, CSS ellipsis only. Hover: the square's card; a click: the inspector's summary. Part 2: the title bar drags the
// block (its spot saved in the lineup's layout), an agent card drags into another block or out onto the canvas, and a
// drag over the block lights it as the drop's target. Tab reaches the block and each agent card (M moves one).
import { useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from "react";
import { shortModel } from "../../../lib/modelName";
import { useHover } from "../../../lib/hover/useHover";
import { ModelTakes } from "../../shared/ModelTakes";
import { modelRow, useRoles } from "../../roles/store";
import { SquareHover } from "../hover/square";
import { disableSquare, type Square } from "../workflows/store";
import { agentsOf, B_AGENT, B_FOOT, B_HEAD, type BlockAgent, type BlockBox } from "./blockLayout";
import { selectBlock, setMenu, toggleFold, useMenu } from "./blockState";
import { startDrag } from "./drag";
import { dropTo } from "./dropTo";
import { useHotTarget } from "./keyMove";
import { moveBlock } from "./opsSquare";

const isAuto = (m: string) => !m || m === "auto" || m === "measured";

function AgentRow({ a, from }: { a: BlockAgent; from: string }) {
  const row = useRoles((s) => modelRow(s, a.model));
  const down = (e: PointerEvent<HTMLDivElement>) => startDrag(e, { kind: "agent", bio: a.bio, from }, a.bio, dropTo({ kind: "agent", bio: a.bio, from }));
  return (
    <div className="blk-agent" style={{ height: B_AGENT }} data-testid="block-agent" data-bio={a.bio} data-from={from} data-lead={a.lead || undefined}
         tabIndex={0} onPointerDown={down} aria-label={`${a.bio} in ${from}: drag it into another block, or out to take it out (M moves it, Delete asks)`}>
      <b className="blk-agent-role">{a.bio}{a.lead ? <span className="muted mono"> · lead</span> : null}</b>
      <div className="blk-agent-model mono">
        <span className="blk-model-name">{isAuto(a.model) ? "auto: picked per task" : shortModel(a.model)}</span>
        {row && <ModelTakes row={row} />}
      </div>
    </div>
  );
}

/** The title bar's drag: the block follows the pointer (in canvas units), and lands in the lineup's layout. */
function useMove(b: BlockBox): { off: { x: number; y: number }; down: (e: PointerEvent<HTMLDivElement>) => void; moved: () => boolean } {
  const [off, setOff] = useState({ x: 0, y: 0 });
  const was = useRef(false);
  const down = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || (e.target as Element).closest("button")) return;
    e.stopPropagation();
    e.preventDefault(); // the title bar drags the block: no text selection
    const el = e.currentTarget.closest<HTMLElement>(".blk");
    const zoom = el ? el.getBoundingClientRect().width / b.w || 1 : 1;
    const x0 = e.clientX, y0 = e.clientY;
    was.current = false;
    const move = (m: globalThis.PointerEvent) => {
      const dx = (m.clientX - x0) / zoom, dy = (m.clientY - y0) / zoom;
      if (!was.current && Math.hypot(dx, dy) < 4) return;
      was.current = true;
      setOff({ x: dx, y: dy });
    };
    const up = (u: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setOff({ x: 0, y: 0 });
      if (!was.current) return;
      const to = { x: Math.round(Math.max(0, b.x + (u.clientX - x0) / zoom)), y: Math.round(Math.max(0, b.y + (u.clientY - y0) / zoom)) };
      moveBlock(b.ref, b.placed ? { x: b.x, y: b.y } : undefined, to);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return { off, down, moved: () => was.current };
}

export function SquareBlock({ q, b, lineup, selected }: { q: Square; b: BlockBox; lineup: string; selected: boolean }) {
  const hv = useHover("square", q.ref, () => <SquareHover sqRef={q.ref} />);
  const t = hv.titles;
  const hot = useHotTarget() === `square:${q.ref}`;
  const menu = useMenu() === q.ref;
  const mv = useMove(b);
  const open = (e: MouseEvent) => (e.stopPropagation(), !mv.moved() && selectBlock(q.ref));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter" || e.key === " ") (e.preventDefault(), selectBlock(q.ref));
  };
  const off = q.when_mode === "off";
  const lines: [string, string][] = [["TAKES", q.takes.join(", ") || "text"], ["GIVES", q.gives.join(", ") || "-"], ["COSTS", q.costs]];
  return (
    <div className="blk" role="button" tabIndex={0} style={{ left: b.x + mv.off.x, top: b.y + mv.off.y, width: b.w, height: b.h }} onClick={open} onKeyDown={onKey}
         onPointerDown={(e) => e.stopPropagation()} data-testid="block" data-kind="square" data-ref={q.ref} data-open={b.open || undefined}
         data-engine={q.engine} data-selected={selected || undefined} data-connected={!off || undefined} data-drop-hot={hot || undefined}
         data-moving={mv.off.x || mv.off.y ? true : undefined} aria-label={`block ${q.ref}: ${q.does}${off ? " (not connected)" : ""}`} {...hv.props}>
      <div className="blk-head" style={{ height: B_HEAD }} onPointerDown={mv.down} data-testid="block-head">
        <div className="blk-row">
          <button className="lg-chev" onClick={(e) => (e.stopPropagation(), toggleFold(lineup, q.ref))} data-testid="block-toggle" data-hover-skip
                  aria-expanded={b.open} aria-label={b.open ? `Fold ${q.ref} to its lines` : `Open ${q.ref}: its agents`}>{b.open ? "▾" : "▸"}</button>
          <b className="blk-name mono" data-testid="block-name">{q.ref}</b>
          <span className="spacer" />
          <button className="icon-btn blk-more" onClick={(e) => (e.stopPropagation(), setMenu(menu ? "" : q.ref))} data-testid="block-more" data-hover-skip
                  aria-haspopup="menu" aria-expanded={menu} aria-label={`${q.ref}: its menu (Connect to main, When, Disconnect, Take it off)`}>⋯</button>
          <button className="icon-btn blk-x" onClick={(e) => (e.stopPropagation(), void disableSquare(q.ref))} data-testid="block-x" data-hover-skip
                  aria-label={`Take ${q.ref} off: main stops handing it work (the file stays)`} title={t ? `Take ${q.ref} off this lineup` : undefined}>×</button>
        </div>
        <div className="blk-purpose" data-testid="block-purpose" title={t ? q.does : undefined}>{q.does || "no purpose line yet"}</div>
      </div>
      <div className="blk-body">
        {b.open ? agentsOf(q).map((a, i) => <AgentRow key={`${a.bio}-${i}`} a={a} from={q.ref} />) : (
          <dl className="blk-lines">
            {lines.map(([k, v]) => <div key={k}><dt className="mono">{k}</dt><dd className="mono" title={t ? v : undefined}>{v}</dd></div>)}
          </dl>
        )}
      </div>
      <div className="blk-foot mono" style={{ height: B_FOOT }} data-testid="block-foot">
        {off ? <span className="blk-foot-off" data-testid="block-unconnected">not connected: main never uses it</span> : (
          <><span className="blk-foot-limits">{q.limits}</span><span className="blk-foot-cost" data-tenant={q.tenant || undefined}>
            {q.tenant === "all" ? "tenant credits" : `band ${q.band}${q.cap_usd != null ? ` · cap $${q.cap_usd}` : ""}${q.tenant === "some" ? " · + tenant credits" : ""}`}</span></>
        )}
      </div>
    </div>
  );
}
