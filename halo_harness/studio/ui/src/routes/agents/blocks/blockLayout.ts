// Where the square blocks sit on the Cast canvas (3.3.16.3): one column to the right of the lineup's tiers, main's card
// on the left; a block is as tall as what it shows -- open: its title bar, one row per agent of its lineup, its footer;
// folded: the title bar and the 3.3.16.0 card's lines. Rows have fixed heights, so nothing inside is ever squished. Pure.
import type { Square } from "../workflows/store";

export const BLOCK_W = 320;
export const B_HEAD = 56; // the name, then the purpose line
export const B_AGENT = 46; // the role, then its model and what the model takes
const B_GAP = 6;
const B_PAD = 10;
export const B_FOOT = 30;
const B_LINE = 18; // a folded block's TAKES / GIVES / COSTS lines
const COL_GAP = 96; // between the tiers and the blocks: room for main's lines
const ROW_GAP = 22;

export type BlockAgent = { bio: string; model: string; lead: boolean };
export type BlockBox = { ref: string; x: number; y: number; w: number; h: number; open: boolean };

/** The agents inside a square: its lead, then its members; a lineup name is one row naming it. */
export function agentsOf(q: Square): BlockAgent[] {
  const l = q.lineup as { members?: unknown } | string | null;
  if (typeof l === "string" && l.trim()) return [{ bio: `lineup ${l}`, model: "", lead: true }];
  const out: BlockAgent[] = q.lead ? [{ bio: q.lead.bio, model: q.lead.model || "", lead: true }] : [];
  const members = l && typeof l === "object" && Array.isArray(l.members) ? l.members : [];
  for (const m of members as unknown[]) {
    if (typeof m === "string" && m) out.push({ bio: m, model: "", lead: false });
    else if (m && typeof m === "object" && (m as { bio?: unknown }).bio)
      out.push({ bio: String((m as { bio: unknown }).bio), model: String((m as { model?: unknown }).model || ""), lead: false });
  }
  return out.length ? out : [{ bio: "the session's lineup", model: "", lead: true }];
}

export function blockHeight(q: Square, open: boolean): number {
  if (!open) return B_HEAD + B_PAD + 3 * B_LINE + B_PAD + B_FOOT;
  const n = agentsOf(q).length;
  return B_HEAD + B_PAD + n * B_AGENT + (n - 1) * B_GAP + B_PAD + B_FOOT;
}

/** The blocks in one column from `x0`, `y0`, in the board's order. */
export function placeBlocks(squares: Square[], folded: string[], x0: number, y0: number): BlockBox[] {
  let y = y0;
  return squares.map((q) => {
    const open = !folded.includes(q.ref);
    const h = blockHeight(q, open);
    const b = { ref: q.ref, x: x0 + COL_GAP, y, w: BLOCK_W, h, open };
    y += h + ROW_GAP;
    return b;
  });
}

/** main's line into a block, crossing no card: from the card's right edge into the gap after main's tier, down under
 *  the tiers (`below`), across to the blocks' column and up into the block's title bar -- one bus all blocks share. */
export function blockEdge(from: { x: number; y: number }, b: BlockBox, below: number): string {
  const gx = from.x + 36, lx = b.x - 32, ty = b.y + B_HEAD / 2;
  return `M${from.x} ${from.y} H${gx} V${below} H${lx} V${ty} H${b.x}`;
}
