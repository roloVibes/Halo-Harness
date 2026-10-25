// The Artboards canvas geometry (3.0.7.0 R3b): the card width, the device a
// prototype is previewed at (the classic page's phone / tablet / desktop
// sizes), the frame a device draws at on a card, the height a card takes in
// the flow, and the flow itself (a card with no saved place goes into rows).
// 3.2.2.0 R5: `dropRoom` -- a card dropped on another never covers it: the
// cards it lands on step aside (lib/geometry.ts `nudgeApart`, the canvas as
// the bounds).
import { nudgeApart, type Box } from "../../lib/geometry";
import type { Artboard, Pos } from "./types";

export const CARD_W = 380;
export const FRAME_W = 356;
const FRAME_MAX_H = 420;
export const GAP = 40;
const PER_ROW = 3;

export type Device = "phone" | "tablet" | "desktop";
export const DEVICES: Record<Device, { w: number; h: number; label: string }> = {
  phone: { w: 390, h: 844, label: "Phone 390" },
  tablet: { w: 820, h: 1100, label: "Tablet 820" },
  desktop: { w: 1280, h: 800, label: "Desktop 1280" },
};
export const DEVICE_IDS = Object.keys(DEVICES) as Device[];
export const isDevice = (v: unknown): v is Device => typeof v === "string" && v in DEVICES;

/** A prototype's frame on a card: its scale and its drawn size. */
export function frameOf(dev: Device): { s: number; w: number; h: number } {
  const d = DEVICES[dev];
  const s = Math.min(FRAME_W / d.w, FRAME_MAX_H / d.h);
  return { s, w: Math.round(d.w * s), h: Math.round(d.h * s) };
}

/** The rows a card takes in the flow: its frame plus the title and the footer. */
export const slotH = (dev: Device) => Math.max(400, frameOf(dev).h + 190);

export function flow(boards: Artboard[], saved: Record<string, Pos>, dev: Device): Record<string, Pos> {
  const out: Record<string, Pos> = {};
  const h = slotH(dev);
  let i = 0;
  for (const a of boards) {
    if (saved[a.id]) out[a.id] = saved[a.id];
    else {
      out[a.id] = { x: 24 + (i % PER_ROW) * (CARD_W + GAP), y: 24 + Math.floor(i / PER_ROW) * h };
      i += 1;
    }
  }
  return out;
}

/** Places for `fresh` artboards: one row under every card already on the canvas. */
export function rowUnder(boards: Artboard[], saved: Record<string, Pos>, dev: Device, fresh: string[]): Record<string, Pos> {
  const old = flow(boards.filter((a) => !fresh.includes(a.id)), saved, dev);
  const y = Math.max(24 - slotH(dev), ...Object.values(old).map((p) => p.y)) + slotH(dev);
  const out: Record<string, Pos> = {};
  fresh.forEach((id, i) => (out[id] = { x: 24 + i * (CARD_W + GAP), y }));
  return out;
}

/** The places that change when artboard `id` lands at `at` (it was at `from`): its own, and every card it overlaps, moved aside. */
export function dropRoom(boards: Artboard[], saved: Record<string, Pos>, dev: Device, id: string, at: Pos, from?: Pos): Record<string, Pos> {
  const h = slotH(dev) - GAP;
  const box = (p: Pos): Box => ({ x: p.x, y: p.y, w: CARD_W, h });
  const placed = flow(boards, saved, dev);
  const others: Record<string, Box> = {};
  for (const a of boards) if (a.id !== id && placed[a.id]) others[a.id] = box(placed[a.id]);
  const after = nudgeApart(box(at), others, { x: 0, y: 0, w: 1e6, h: 1e6 }, { minW: CARD_W, minH: h, gap: GAP / 2, from: from ? box(from) : undefined });
  const patch: Record<string, Pos> = { [id]: at };
  for (const k of Object.keys(others)) if (after[k].x !== others[k].x || after[k].y !== others[k].y) patch[k] = { x: Math.round(after[k].x), y: Math.round(after[k].y) };
  return patch;
}
