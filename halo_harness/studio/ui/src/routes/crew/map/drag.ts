// The Map tab's two drags (3.6.0.0 R3; the mock-up's dragRow / connectDrag), real pointer events, no library:
// - a row of the list (agents, workflows) dragged onto the map: while it moves the drop places light up and SAY what a
//   drop does -- a box "drop: main hands work to it" (or "<box> hands work to it"), the strip "drop: add, connect
//   later" -- the one under the pointer marked; a drop on a box adds it with a line from that box (its When card opens),
//   anywhere else on the map adds it under "Not connected yet";
// - a box's connect dot dragged to another box: a rubber line follows the pointer, the boxes it may go to light up; a
//   drop connects them (a strip box's dot dropped on a box: that box hands work to it); a click without a move opens the
//   list of targets instead (the keyboard path: Enter on the dot).
// A drag moves only past 5 px; Escape cancels it. Nothing here is drawn by React: the attributes come and go with it.
import type { PointerEvent as RPointerEvent } from "react";
import { addBox, connect, maps, setPick } from "./mapStore";

const MOVE = 5;
const DROP_BOX = "[data-map-box]";
const STRIP = "[data-testid=map-strip]";
const CANVAS = "[data-testid=map-scroll]";

function clear(): void {
  document.querySelectorAll("[data-drop]").forEach((el) => el.removeAttribute("data-drop"));
  document.querySelectorAll("[data-drop-on]").forEach((el) => el.removeAttribute("data-drop-on"));
  const g = document.querySelector<HTMLElement>("[data-testid=map-drag-ghost]");
  if (g) g.hidden = true;
  const r = document.querySelector<SVGPathElement>("[data-testid=map-rubber] path");
  if (r) r.setAttribute("d", "");
}

function track(e: PointerEvent, move: (m: PointerEvent) => void, end: (m: PointerEvent | null) => void): void {
  const x0 = e.clientX, y0 = e.clientY;
  let moved = false;
  const mv = (m: PointerEvent) => {
    if (!moved && Math.hypot(m.clientX - x0, m.clientY - y0) < MOVE) return;
    moved = true;
    move(m);
  };
  const up = (m: PointerEvent) => (stop(), clear(), end(moved ? m : null));
  const key = (k: KeyboardEvent) => { if (k.key === "Escape") (stop(), clear()); };
  const stop = () => {
    window.removeEventListener("pointermove", mv);
    window.removeEventListener("pointerup", up);
    window.removeEventListener("keydown", key);
  };
  window.addEventListener("pointermove", mv);
  window.addEventListener("pointerup", up);
  window.addEventListener("keydown", key);
}

const under = (m: PointerEvent, sel: string): HTMLElement | null =>
  (document.elementFromPoint(m.clientX, m.clientY) as HTMLElement | null)?.closest?.(sel) || null;

export function dragRow(e: RPointerEvent, kind: "agent" | "workflow", ref: string): void {
  if (e.button !== 0 || maps.get().locked || (e.target as HTMLElement).closest("button")) return;
  e.preventDefault();
  const label = `${kind} ${ref}`;
  track(e.nativeEvent, (m) => {
    const g = document.querySelector<HTMLElement>("[data-testid=map-drag-ghost]");
    if (g) {
      g.hidden = false;
      g.textContent = label;
      g.style.left = `${m.clientX + 14}px`;
      g.style.top = `${m.clientY + 10}px`;
    }
    document.querySelectorAll<HTMLElement>(`[data-testid=map-world] ${DROP_BOX}`).forEach((b) => {
      if (!b.dataset.ghost) b.dataset.drop = `drop: ${b.dataset.mapBox === "main" ? "main" : b.dataset.name} hands work to it`;
    });
    const strip = document.querySelector<HTMLElement>(STRIP);
    if (strip) strip.dataset.drop = "drop: add, connect later";
    document.querySelectorAll("[data-drop-on]").forEach((el) => el.removeAttribute("data-drop-on"));
    const on = under(m, `[data-testid=map-world] ${DROP_BOX}`) || under(m, STRIP);
    if (on) on.dataset.dropOn = "1";
  }, (m) => {
    if (!m) return;
    const box = under(m, `[data-testid=map-world] ${DROP_BOX}`);
    if (box && !box.dataset.ghost) void addBox(kind, ref, box.dataset.mapBox);
    else if (under(m, STRIP) || under(m, CANVAS)) void addBox(kind, ref);
  });
}

export function dragDot(e: RPointerEvent, from: string, inStrip: boolean): void {
  if (e.button !== 0 || maps.get().locked) return;
  e.preventDefault();
  e.stopPropagation();
  const dot = e.currentTarget as HTMLElement;
  track(e.nativeEvent, (m) => {
    const r = dot.getBoundingClientRect();
    document.querySelector("[data-testid=map-rubber] path")?.setAttribute("d", `M${r.left + r.width / 2} ${r.top + r.height / 2} L${m.clientX} ${m.clientY}`);
    document.querySelectorAll<HTMLElement>(DROP_BOX).forEach((b) => {
      if (b.dataset.mapBox !== from && !b.dataset.ghost && !(inStrip && b.closest(STRIP)) && !(b.dataset.mapBox === "main" && !inStrip))
        b.dataset.drop = inStrip ? `drop: ${b.dataset.name} hands work to it` : "drop: hands work to this";
    });
    document.querySelectorAll("[data-drop-on]").forEach((el) => el.removeAttribute("data-drop-on"));
    const on = under(m, DROP_BOX);
    if (on?.dataset.drop) on.dataset.dropOn = "1";
  }, (m) => {
    if (!m) return setPick(from);
    const box = under(m, DROP_BOX);
    const to = box?.dataset.mapBox;
    if (!to || to === from || box?.dataset.ghost) return;
    const toInStrip = !!box?.closest(STRIP);
    void (inStrip && !toInStrip ? connect(to, from) : connect(from, to));
  });
}
