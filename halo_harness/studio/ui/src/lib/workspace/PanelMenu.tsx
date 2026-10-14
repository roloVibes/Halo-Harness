// A panel's "..." menu: Float (or Dock), Collapse (or Open), Reset this
// panel, Settings (the Inspector) and Help (the ? popover). It renders in a
// portal so a small panel never clips it; a choice, Esc or a click outside
// closes it, and the arrow keys move between the items.
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../ui/Icon";
import { Kbd } from "../ui/Kbd";

export type MenuItem = { id: string; label: string; icon: string; kbd?: string; run: () => void };

const W = 228;

export function PanelMenu({ title, items }: { title: string; items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ left: 0, top: 0 });
  const btn = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    setPos({ left: Math.max(8, Math.min(r.right - W, window.innerWidth - W - 8)), top: Math.max(8, Math.min(r.bottom + 6, window.innerHeight - 236)) });
    box.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus({ preventScroll: true });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const off = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!box.current?.contains(t) && !btn.current?.contains(t)) setOpen(false);
    };
    window.addEventListener("pointerdown", off, true);
    return () => window.removeEventListener("pointerdown", off, true);
  }, [open]);

  const onKey = (e: KeyboardEvent) => {
    const all = Array.from(box.current?.querySelectorAll<HTMLElement>("[role=menuitem]") || []);
    const i = all.indexOf(document.activeElement as HTMLElement);
    if (e.key === "Escape") {
      setOpen(false);
      btn.current?.focus({ preventScroll: true });
    } else if (e.key === "ArrowDown") all[(i + 1) % all.length]?.focus();
    else if (e.key === "ArrowUp") all[(i - 1 + all.length) % all.length]?.focus();
    else return;
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <>
      <button
        ref={btn}
        className="icon-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        title="More: float, collapse, reset, settings, help"
        aria-label={`${title}: more`}
        data-testid="panel-menu-btn"
        onClick={() => setOpen(!open)}
      >
        <Icon name="more" />
      </button>
      {open &&
        createPortal(
          <div ref={box} className="menu glass panel-menu" role="menu" aria-label={`${title} panel`} style={{ left: pos.left, top: pos.top, width: W }} onKeyDown={onKey} data-testid="panel-menu">
            {items.map((it) => (
              <button
                key={it.id}
                role="menuitem"
                className="menu-item"
                data-item={it.id}
                onClick={() => {
                  setOpen(false);
                  it.run();
                }}
              >
                <Icon name={it.icon} />
                <span className="menu-label">{it.label}</span>
                {it.kbd && <Kbd keys={it.kbd} />}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
