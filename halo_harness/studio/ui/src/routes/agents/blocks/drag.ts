// The blocks' drag (3.3.16.3, docs/STUDIO-blocks.md "Drag and drop"): a pointer drag -- press, move four pixels, release
// -- so it is one gesture with a mouse, a pen or a test's real pointer, with a label under the pointer while it moves and
// the target it would land on lit. What it carries: a workflow or a block template from the library, a bio, a square's
// agent, or main's edge handle (a line to draw). Where it lands: a square block, a tier box (a card in it counts as its
// tier), the canvas's empty space, or the Workflows board. A release that moved nowhere is a click (nothing happens here).
import type { PointerEvent } from "react";
import { createStore, useStore } from "../../../lib/store";
import { roles } from "../../roles/store";

export type Payload =
  | { kind: "workflow"; ref: string }
  | { kind: "template"; name: string }
  | { kind: "bio"; bio: string }
  | { kind: "agent"; bio: string; from: string }
  | { kind: "card"; id: string; bio: string }
  | { kind: "line"; from: string };
export type Target = { kind: "square"; ref: string } | { kind: "tier"; name: string } | { kind: "canvas" } | { kind: "board" } | null;
type State = { payload: Payload | null; label: string; x: number; y: number; target: Target };

export const dragging = createStore<State>({ payload: null, label: "", x: 0, y: 0, target: null });
export const useDrag = <S,>(pick: (s: State) => S): S => useStore(dragging, pick);
export const targetKey = (t: Target): string => (!t ? "" : t.kind === "square" ? `square:${t.ref}` : t.kind === "tier" ? `tier:${t.name}` : t.kind);

/** What sits under the point: a square block, a tier box (or a card in one), the canvas, the board. */
export function targetAt(x: number, y: number): Target {
  // the topmost element that is not what is being dragged (a card follows the pointer; so does a moving block)
  const el = (document.elementsFromPoint(x, y) as HTMLElement[]).find((e) => !e.closest("[data-drag-ghost], [data-dragging], [data-moving]")) || null;
  if (!el) return null;
  const sq = el.closest<HTMLElement>('[data-testid="block"][data-kind="square"]');
  if (sq?.dataset.ref) return { kind: "square", ref: sq.dataset.ref };
  const tier = el.closest<HTMLElement>('[data-testid="roles-tier"]');
  if (tier?.dataset.tier && !tier.dataset.implicit) return { kind: "tier", name: tier.dataset.tier };
  const card = el.closest<HTMLElement>('[data-testid="roles-card"]');
  if (card?.dataset.id) {
    const t = roles.get().graph?.tiers.find((x) => x.node_ids.includes(card.dataset.id!));
    if (t && !t.implicit) return { kind: "tier", name: t.name };
  }
  if (el.closest(".rc-scroll")) return { kind: "canvas" };
  if (el.closest('[data-testid="wf-board"]')) return { kind: "board" };
  return null;
}

/** Start a drag from a pointer down; `drop` gets where it landed (and the release point) when it moved. */
export function startDrag(ev: PointerEvent<HTMLElement>, payload: Payload, label: string, drop: (t: Target, at: { x: number; y: number }) => void): void {
  if (ev.button !== 0) return;
  ev.stopPropagation();
  ev.preventDefault(); // no text selection, no native drag of a selection: the pointer is the drag
  window.getSelection()?.removeAllRanges();
  const x0 = ev.clientX, y0 = ev.clientY;
  let moved = false;
  const move = (m: globalThis.PointerEvent) => {
    if (!moved && Math.hypot(m.clientX - x0, m.clientY - y0) < 5) return;
    if (!moved) m.preventDefault();
    moved = true;
    dragging.update(() => ({ payload, label, x: m.clientX, y: m.clientY, target: targetAt(m.clientX, m.clientY) }));
  };
  const up = (u: globalThis.PointerEvent) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    window.removeEventListener("pointercancel", up);
    dragging.update(() => ({ payload: null, target: null }));
    if (moved && u.type === "pointerup") drop(targetAt(u.clientX, u.clientY), { x: u.clientX, y: u.clientY });
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
  window.addEventListener("pointercancel", up);
}
