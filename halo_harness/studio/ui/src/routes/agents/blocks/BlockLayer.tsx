// The lineup's enabled squares as blocks on the Cast canvas (3.3.16.3 "one board": the tiers and the squares on one
// canvas, main on top). The blocks stand in a column right of the tiers (or where their title bar was dragged: the
// lineup's layout); main's line goes from its card into each connected block's title bar and carries the block's
// "when" as a short label -- hover it for the rule in a sentence, click the line or the label for the When page. A block
// with no line is dashed (SquareBlock). Main's edge handle draws a line: drag it onto a block. GET workflows?lineup= is
// the source (routes/agents/workflows/store.ts): the same squares the Workflows view (W) shows.
import { useEffect, useMemo } from "react";
import { useHover } from "../../../lib/hover/useHover";
import { CARD_H, CARD_W, PAD } from "../../roles/layout";
import { useRoles } from "../../roles/store";
import type { Graph, Pos } from "../../roles/types";
import { WhenHover } from "../hover/when";
import { loadBoard, onBoard, select, useWf, wf, type Square } from "../workflows/store";
import { blockEdge, labelAt, LABEL_W, placeBlocks, type BlockBox } from "./blockLayout";
import { selectBlock, useBlockSel, useFolded } from "./blockState";
import { startDrag } from "./drag";
import { dropTo } from "./dropTo";
import { BlockMenu } from "./BlockMenu";
import { connected, whenLabel } from "./templates";
import { SquareBlock } from "./SquareBlock";

export type Blocks = { boxes: BlockBox[]; w: number; h: number; from: { x: number; y: number } | null; below: number };

export function useSquareBlocks(graph: Graph | null, pos: Record<string, Pos>, lineup: string, tiersRight: number): Blocks {
  const board = useWf((s) => s.board);
  const folded = useFolded(lineup);
  const saved = useRoles((s) => s.positions);
  useEffect(() => void (lineup && loadBoard(lineup)), [lineup]);
  return useMemo(() => {
    const squares = onBoard({ ...wf.get(), board });
    const main = graph?.nodes.find((n) => n.role === "main");
    const mp = main ? pos[main.id] : undefined;
    const boxes = placeBlocks(squares, folded, tiersRight, mp ? Math.max(24, mp.y) : 24, saved);
    const below = Math.max(0, ...Object.values(pos).map((p) => p.y + CARD_H + PAD + 22)); // under every tier box
    const w = Math.max(0, ...boxes.map((b) => b.x + b.w + 40));
    const h = Math.max(0, ...boxes.map((b) => b.y + b.h + 40), boxes.length ? below + 24 : 0);
    return { boxes, w, h, from: mp ? { x: mp.x + CARD_W + PAD, y: mp.y + CARD_H / 2 } : null, below };
  }, [board, folded, graph, pos, tiersRight, saved]);
}

const openWhen = (ref: string) => (selectBlock(ref), select(ref, "when"));

function WhenLabel({ q, b }: { q: Square; b: BlockBox }) {
  const hv = useHover("when", q.ref, () => <WhenHover sqRef={q.ref} />);
  const at = labelAt(b);
  return (
    <button className="blk-when-label mono" style={{ left: at.x, top: at.y, width: LABEL_W }} data-testid="block-when" data-to={q.ref}
            data-mode={q.when_mode || "auto"} onClick={(e) => (e.stopPropagation(), openWhen(q.ref))} onPointerDown={(e) => e.stopPropagation()}
            aria-label={`main -> ${q.ref}: ${q.when_sentence || whenLabel(q)}. Change when`} {...hv.props}>
      {whenLabel(q)}
    </button>
  );
}

function Handle({ at }: { at: { x: number; y: number } }) {
  return (
    <button className="blk-handle" style={{ left: at.x - 7, top: at.y - 7 }} data-testid="block-handle" data-from="main"
            aria-label="main's edge handle: drag it onto a block to draw a line (or use Connect to main in the block's menu)"
            title="Drag onto a block: main hands it work"
            onPointerDown={(e) => startDrag(e, { kind: "line", from: "main" }, "a line from main", dropTo({ kind: "line", from: "main" }))} />
  );
}

export function BlockLayer({ blocks, lineup, w, h }: { blocks: Blocks; lineup: string; w: number; h: number }) {
  const board = useWf((s) => s.board);
  const sel = useBlockSel();
  if (!blocks.boxes.length) return null;
  const sq = (ref: string) => board?.squares.find((x) => x.ref === ref);
  const lines = blocks.boxes.filter((b) => sq(b.ref) && connected(sq(b.ref)!));
  return (
    <>
      {blocks.from && (
        <svg className="blk-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
          {lines.map((b) => <path key={b.ref} className="blk-edge" d={blockEdge(blocks.from!, b, blocks.below)} data-testid="block-edge" data-to={b.ref} />)}
          {lines.map((b) => <path key={`hit-${b.ref}`} className="blk-edge-hit" d={blockEdge(blocks.from!, b, blocks.below)} data-testid="block-edge-hit"
                                  data-to={b.ref} onClick={() => openWhen(b.ref)} />)}
        </svg>
      )}
      {blocks.from && lines.map((b) => <WhenLabel key={`l-${b.ref}`} q={sq(b.ref)!} b={b} />)}
      {blocks.from && <Handle at={blocks.from} />}
      {blocks.boxes.map((b) => {
        const q = sq(b.ref);
        return q ? <SquareBlock key={b.ref} q={q} b={b} lineup={lineup} selected={sel === b.ref} /> : null;
      })}
      <BlockMenu boxes={blocks.boxes} />
    </>
  );
}
