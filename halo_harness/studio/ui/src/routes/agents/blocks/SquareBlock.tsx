// A workflow square as a block on the Cast canvas (3.3.16.3, the owner: "here is the media workflow ... all these agents
// you can combine or add, little blocks in there"): a title bar (the chevron, the square's name, its purpose -- the
// DOES line -- and its `x`), then, open, one small agent card per bio of its lineup (its role, the model's short name,
// what the model takes), folded, the 3.3.16.0 card's TAKES / GIVES / COSTS lines; a footer with its limits and its
// cost band. One fact per row, CSS ellipsis only. Hover: the square's card (3.3.16.1); a click: the inspector's
// summary of the block. The chevron's state is kept per lineup (blockState.ts).
import type { KeyboardEvent, MouseEvent } from "react";
import { shortModel } from "../../../lib/modelName";
import { useHover } from "../../../lib/hover/useHover";
import { ModelTakes } from "../../shared/ModelTakes";
import { modelRow, useRoles } from "../../roles/store";
import { SquareHover } from "../hover/square";
import { disableSquare, type Square } from "../workflows/store";
import { agentsOf, B_AGENT, B_FOOT, B_HEAD, type BlockAgent, type BlockBox } from "./blockLayout";
import { selectBlock, toggleFold } from "./blockState";

const isAuto = (m: string) => !m || m === "auto" || m === "measured";

function AgentRow({ a }: { a: BlockAgent }) {
  const row = useRoles((s) => modelRow(s, a.model));
  return (
    <div className="blk-agent" style={{ height: B_AGENT }} data-testid="block-agent" data-bio={a.bio} data-lead={a.lead || undefined}>
      <b className="blk-agent-role">{a.bio}{a.lead ? <span className="muted mono"> · lead</span> : null}</b>
      <div className="blk-agent-model mono">
        <span className="blk-model-name">{isAuto(a.model) ? "auto: picked per task" : shortModel(a.model)}</span>
        {row && <ModelTakes row={row} />}
      </div>
    </div>
  );
}

export function SquareBlock({ q, b, lineup, selected }: { q: Square; b: BlockBox; lineup: string; selected: boolean }) {
  const hv = useHover("square", q.ref, () => <SquareHover sqRef={q.ref} />);
  const t = hv.titles;
  const open = (e: MouseEvent) => (e.stopPropagation(), selectBlock(q.ref));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter" || e.key === " ") (e.preventDefault(), selectBlock(q.ref));
  };
  const lines: [string, string][] = [["TAKES", q.takes.join(", ") || "text"], ["GIVES", q.gives.join(", ") || "-"], ["COSTS", q.costs]];
  return (
    <div className="blk" role="button" tabIndex={0} style={{ left: b.x, top: b.y, width: b.w, height: b.h }} onClick={open} onKeyDown={onKey}
         onPointerDown={(e) => e.stopPropagation()} data-testid="block" data-kind="square" data-ref={q.ref} data-open={b.open || undefined}
         data-engine={q.engine} data-selected={selected || undefined} aria-label={`block ${q.ref}: ${q.does}`} {...hv.props}>
      <div className="blk-head" style={{ height: B_HEAD }}>
        <div className="blk-row">
          <button className="lg-chev" onClick={(e) => (e.stopPropagation(), toggleFold(lineup, q.ref))} data-testid="block-toggle" data-hover-skip
                  aria-expanded={b.open} aria-label={b.open ? `Fold ${q.ref} to its lines` : `Open ${q.ref}: its agents`}>{b.open ? "▾" : "▸"}</button>
          <b className="blk-name mono" data-testid="block-name">{q.ref}</b>
          <span className="spacer" />
          <button className="icon-btn blk-x" onClick={(e) => (e.stopPropagation(), void disableSquare(q.ref))} data-testid="block-x" data-hover-skip
                  aria-label={`Take ${q.ref} off: main stops handing it work (the file stays)`} title={t ? `Take ${q.ref} off this lineup` : undefined}>×</button>
        </div>
        <div className="blk-purpose" data-testid="block-purpose" title={t ? q.does : undefined}>{q.does || "no purpose line yet"}</div>
      </div>
      <div className="blk-body">
        {b.open ? agentsOf(q).map((a) => <AgentRow key={a.bio} a={a} />) : (
          <dl className="blk-lines">
            {lines.map(([k, v]) => <div key={k}><dt className="mono">{k}</dt><dd className="mono" title={t ? v : undefined}>{v}</dd></div>)}
          </dl>
        )}
      </div>
      <div className="blk-foot mono" style={{ height: B_FOOT }} data-testid="block-foot">
        <span className="blk-foot-limits">{q.limits}</span><span className="blk-foot-cost">band {q.band}{q.cap_usd != null ? ` · cap $${q.cap_usd}` : ""}</span>
      </div>
    </div>
  );
}
