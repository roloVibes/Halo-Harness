// A block's menu (3.3.16.3): its title bar's ⋯ opens it beside the block -- the keyboard's way to everything a drag
// does to a block: Connect to main (a block with no line; the confirm card says what it writes), When... (its page),
// Disconnect (main stops using it; the block stays, dashed), Take it off this lineup (asks in the inspector). Esc or a
// click elsewhere closes it; the first item takes the focus when it opens. Nothing opens it but the ⋯.
import { useEffect, useRef } from "react";
import { select, squareOf, useWf } from "../workflows/store";
import type { BlockBox } from "./blockLayout";
import { selectBlock, setMenu, useMenu } from "./blockState";
import { offerConnect, setWhen } from "./opsSquare";

export function BlockMenu({ boxes }: { boxes: BlockBox[] }) {
  const ref = useMenu();
  const q = useWf((s) => squareOf(s, ref));
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref) return;
    box.current?.querySelector<HTMLButtonElement>("button")?.focus({ preventScroll: true });
    const away = (e: PointerEvent) => !box.current?.contains(e.target as Node) && !(e.target as Element)?.closest?.('[data-testid="block-more"]') && setMenu("");
    const esc = (e: KeyboardEvent) => e.key === "Escape" && (e.stopPropagation(), setMenu(""));
    window.addEventListener("pointerdown", away, true);
    window.addEventListener("keydown", esc, true);
    return () => (window.removeEventListener("pointerdown", away, true), window.removeEventListener("keydown", esc, true));
  }, [ref]);
  const b = boxes.find((x) => x.ref === ref);
  if (!ref || !q || !b) return null;
  const off = q.when_mode === "off";
  const go = (fn: () => void) => () => (setMenu(""), fn());
  const items: [string, string, () => void][] = [
    ...(off ? [["connect", "Connect to main...", go(() => offerConnect(q.ref))] as [string, string, () => void]] : []),
    ["when", "When...", go(() => (selectBlock(q.ref), select(q.ref, "when")))],
    ...(off ? [] : [["disconnect", "Disconnect from main", go(() => void setWhen(q.ref, { mode: "off" }, "disconnected"))] as [string, string, () => void]]),
    ["remove", "Take it off this lineup...", go(() => (selectBlock(q.ref), select(q.ref, "remove")))],
  ];
  return (
    <div className="blk-menu" ref={box} role="menu" aria-label={`${q.ref}: its menu`} data-testid="block-menu" data-ref={q.ref}
         style={{ left: b.x + b.w - 212, top: b.y + 30 }} onPointerDown={(e) => e.stopPropagation()}>
      {items.map(([id, label, fn]) => (
        <button key={id} role="menuitem" className="blk-menu-item" onClick={fn} data-testid={`block-menu-${id}`}>{label}</button>
      ))}
    </div>
  );
}
