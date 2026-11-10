// The lineup's enabled squares as blocks on the Cast canvas (3.3.16.3 "one board": the tiers and the squares on one
// canvas, main on top). The blocks stand in a column right of the tiers; main's line goes from its card into each block's
// title bar (main may hand that block work). GET workflows is the source (routes/agents/workflows/store.ts): the same
// squares the Workflows view (W) shows, filtered there with the library open.
import { useEffect, useMemo } from "react";
import { CARD_H, CARD_W, PAD } from "../../roles/layout";
import type { Graph, Pos } from "../../roles/types";
import { loadBoard, onBoard, useWf, wf } from "../workflows/store";
import { blockEdge, placeBlocks, type BlockBox } from "./blockLayout";
import { useBlockSel, useFolded } from "./blockState";
import { SquareBlock } from "./SquareBlock";

export type Blocks = { boxes: BlockBox[]; w: number; h: number; from: { x: number; y: number } | null; below: number };

export function useSquareBlocks(graph: Graph | null, pos: Record<string, Pos>, lineup: string, tiersRight: number): Blocks {
  const board = useWf((s) => s.board);
  const folded = useFolded(lineup);
  useEffect(() => void loadBoard(), [lineup]);
  return useMemo(() => {
    const squares = onBoard({ ...wf.get(), board });
    const main = graph?.nodes.find((n) => n.role === "main");
    const mp = main ? pos[main.id] : undefined;
    const boxes = placeBlocks(squares, folded, tiersRight, mp ? Math.max(24, mp.y) : 24);
    const below = Math.max(0, ...Object.values(pos).map((p) => p.y + CARD_H + PAD + 22)); // under every tier box
    const w = Math.max(0, ...boxes.map((b) => b.x + b.w + 40));
    const h = Math.max(0, ...boxes.map((b) => b.y + b.h + 40), boxes.length ? below + 24 : 0);
    return { boxes, w, h, from: mp ? { x: mp.x + CARD_W + PAD, y: mp.y + CARD_H / 2 } : null, below };
  }, [board, folded, graph, pos, tiersRight]);
}

export function BlockLayer({ blocks, lineup, w, h }: { blocks: Blocks; lineup: string; w: number; h: number }) {
  const board = useWf((s) => s.board);
  const sel = useBlockSel();
  if (!blocks.boxes.length) return null;
  return (
    <>
      {blocks.from && (
        <svg className="blk-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
          {blocks.boxes.map((b) => <path key={b.ref} className="blk-edge" d={blockEdge(blocks.from!, b, blocks.below)} data-testid="block-edge" data-to={b.ref} />)}
        </svg>
      )}
      {blocks.boxes.map((b) => {
        const q = board?.squares.find((x) => x.ref === b.ref);
        return q ? <SquareBlock key={b.ref} q={q} b={b} lineup={lineup} selected={sel === b.ref} /> : null;
      })}
    </>
  );
}
