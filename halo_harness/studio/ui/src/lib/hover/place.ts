// Where the hover card sits (pure; lib/ui/HoverCard.tsx measures and calls it after the card draws, NodeMenu's way):
// beside its box -- right, then left, then below, then above -- the first side where the whole card fits inside the
// window with an 8 px margin, so it never covers the box it describes; slid along that side to stay inside. When no
// side holds it whole (a tiny window), the side with the most room, kept inside the window.
export type Box = { left: number; top: number; right: number; bottom: number };
export type Spot = { left: number; top: number; side: "right" | "left" | "below" | "above" };

export const MARGIN = 8;
export const GAP = 8;

export function place(a: Box, w: number, h: number, vw: number, vh: number): Spot {
  const x = (v: number) => Math.max(MARGIN, Math.min(v, vw - w - MARGIN));
  const y = (v: number) => Math.max(MARGIN, Math.min(v, vh - h - MARGIN));
  if (a.right + GAP + w <= vw - MARGIN) return { left: a.right + GAP, top: y(a.top), side: "right" };
  if (a.left - GAP - w >= MARGIN) return { left: a.left - GAP - w, top: y(a.top), side: "left" };
  if (a.bottom + GAP + h <= vh - MARGIN) return { left: x(a.left), top: a.bottom + GAP, side: "below" };
  if (a.top - GAP - h >= MARGIN) return { left: x(a.left), top: a.top - GAP - h, side: "above" };
  const room = { right: vw - a.right, left: a.left, below: vh - a.bottom, above: a.top };
  const side = (Object.keys(room) as Spot["side"][]).reduce((best, k) => (room[k] > room[best] ? k : best), "right" as Spot["side"]);
  if (side === "right") return { left: x(a.right + GAP), top: y(a.top), side };
  if (side === "left") return { left: x(a.left - GAP - w), top: y(a.top), side };
  if (side === "below") return { left: x(a.left), top: y(a.bottom + GAP), side };
  return { left: x(a.left), top: y(a.top - GAP - h), side };
}
