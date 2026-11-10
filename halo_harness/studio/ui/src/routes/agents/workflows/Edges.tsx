// The board's geometry and its edges (3.3.16.0 R3). Every size is a multiple of the 12 px grid: a square is 240 x 140,
// 24 px apart, main's node sits at the top left and the squares fill rows under it, never overlapping. Main's lines to
// the squares are the allow-list, drawn as the Instrument's edges (docs/design/studio-instrument/PROPOSAL.md): still at
// rest; only the line toward the square at work carries a moving dash (data-live), and only one square glows at a time.
export const GRID = 12;
export const CARD_W = 240;
export const CARD_H = 140;
export const GAP = 24;
export const PAD = 24;
export const MAIN_W = 240;
export const MAIN_H = 48;
export const TOP = PAD + MAIN_H + 72; // the first row of squares, 72 px under main (the bus runs in between)

export type Box = { ref: string; x: number; y: number; w: number; h: number };

/** The squares' boxes for a board `width` px wide, in the enabled order (left to right, then down). */
export function layout(refs: string[], width: number): { boxes: Box[]; height: number; cols: number } {
  const cols = Math.max(1, Math.floor((Math.max(width, CARD_W + 2 * PAD) - 2 * PAD + GAP) / (CARD_W + GAP)));
  const boxes = refs.map((ref, i) => ({
    ref, w: CARD_W, h: CARD_H, x: PAD + (i % cols) * (CARD_W + GAP), y: TOP + Math.floor(i / cols) * (CARD_H + GAP),
  }));
  const rows = Math.ceil(refs.length / cols);
  return { boxes, cols, height: rows ? TOP + rows * (CARD_H + GAP) + PAD : TOP };
}

/** main's bottom centre -> down to the bus -> across -> down into the square's top centre. */
export function edgePath(b: Box): string {
  const sx = PAD + MAIN_W / 2;
  const sy = PAD + MAIN_H;
  const cx = b.x + b.w / 2;
  const bus = TOP - 36;
  return b.y === TOP ? `M ${sx} ${sy} V ${bus} H ${cx} V ${b.y}` : `M ${sx} ${sy} V ${bus} H ${b.x - GAP / 2} V ${b.y - 18} H ${cx} V ${b.y}`;
}

export function Edges({ boxes, working, width, height }: { boxes: Box[]; working: string; width: number; height: number }) {
  return (
    <svg className="wf-edges" width={width} height={height} aria-hidden="true" data-testid="wf-edges">
      {boxes.map((b) => (
        <path key={b.ref} d={edgePath(b)} className="wf-edge" data-ref={b.ref} data-live={b.ref === working || undefined} />
      ))}
    </svg>
  );
}
