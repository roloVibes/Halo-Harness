// The Artboards canvas geometry (3.0.7.0 R3b): the card width, the device a
// prototype is previewed at (the classic page's phone / tablet / desktop
// sizes), the frame a device draws at on a card, the height a card takes in
// the flow, and the flow itself (a card with no saved place goes into rows).
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
