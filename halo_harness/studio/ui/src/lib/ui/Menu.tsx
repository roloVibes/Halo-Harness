// A small header menu (3.3.2.0 R2): a button that opens a list of rows in a
// portal under it (so a narrow header never clips it). Keyboard first: Enter,
// Space or ArrowDown on the button opens it on its first row; ArrowUp /
// ArrowDown / Home / End move between the rows, Enter runs one, Escape (or
// Tab, or a press outside) closes it and gives the focus back to the button.
// A row may carry a word (what pressing it does), badges and a title; a
// disabled row stays in the list with its words, so the reader sees why.
// 3.3.2.0 R3: a panel's own "..." menu is this one too (lib/workspace/PanelMenu.tsx: a smaller button,
// the list right-aligned under it, a key hint per row).
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
import { Kbd } from "./Kbd";

export type MenuRow = {
  id: string;
  label: string;
  icon?: string;
  /** What pressing the row does, in one or two words ("add", "bring back", "focus"). */
  word?: string;
  badges?: string[];
  title?: string;
  disabled?: boolean;
  testid?: string;
  /** Extra data-* attributes for the row (`{ panel: "fleet-map" }` is `data-panel`). */
  data?: Record<string, string>;
  current?: boolean;
  /** A key hint drawn at the row's end ("?"). */
  kbd?: string;
  run: () => void;
};
export type MenuGroup = { name?: string; rows: MenuRow[] };

type Props = {
  icon: string; label: string; title: string; testid: string; menuTestid: string; groups: MenuGroup[]; width?: number;
  /** 3.3.2.0 R3: the button's class (a panel's is the small icon button), the list's, and its edge under the button. */
  btnClass?: string; menuClass?: string; align?: "left" | "right";
};

const ROWS = "[role=menuitem]:not(:disabled)";

export function Menu({ icon, label, title, testid, menuTestid, groups, width = 280, btnClass = "icon-btn icon-btn-lg", menuClass = "hdr-menu", align = "left" }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ left: 0, top: 0 });
  const btn = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const rows = () => Array.from(box.current?.querySelectorAll<HTMLElement>(ROWS) || []);
  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) btn.current?.focus({ preventScroll: true });
  };

  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    const edge = align === "right" ? r.right - width : r.left;
    setPos({ left: Math.max(8, Math.min(edge, window.innerWidth - width - 8)), top: Math.min(r.bottom + 6, Math.max(8, window.innerHeight - 260)) });
    rows()[0]?.focus({ preventScroll: true });
  }, [open, width]);

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
    const all = rows();
    const i = all.indexOf(document.activeElement as HTMLElement);
    if (e.key === "Escape") close();
    else if (e.key === "Tab") return close(false);
    else if (e.key === "ArrowDown") all[(i + 1) % all.length]?.focus();
    else if (e.key === "ArrowUp") all[(i - 1 + all.length) % all.length]?.focus();
    else if (e.key === "Home") all[0]?.focus();
    else if (e.key === "End") all[all.length - 1]?.focus();
    else return;
    e.preventDefault();
    e.stopPropagation();
  };
  const onBtnKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown" && !open) (e.preventDefault(), setOpen(true));
  };

  return (
    <>
      <button ref={btn} className={btnClass} aria-haspopup="menu" aria-expanded={open} aria-label={label} title={title} data-testid={testid}
              onClick={() => setOpen(!open)} onKeyDown={onBtnKey}>
        <Icon name={icon} />
      </button>
      {open &&
        createPortal(
          <div ref={box} className={`menu glass ${menuClass}`} role="menu" aria-label={label} data-testid={menuTestid} style={{ left: pos.left, top: pos.top, right: "auto", width }} onKeyDown={onKey}>
            {groups.filter((g) => g.rows.length).map((g, gi) => (
              <div key={g.name || gi} className="hdr-menu-group" role="group" aria-label={g.name}>
                {g.name && <div className="hdr-menu-name mono">{g.name}</div>}
                {g.rows.map((r) => (
                  <button
                    key={r.id}
                    role="menuitem"
                    className="menu-item"
                    data-item={r.id}
                    data-testid={r.testid}
                    aria-current={r.current || undefined}
                    {...Object.fromEntries(Object.entries(r.data || {}).map(([k, v]) => ["data-" + k, v]))}
                    disabled={r.disabled}
                    title={r.title}
                    onClick={() => {
                      close();
                      r.run();
                    }}
                  >
                    {r.icon && <Icon name={r.icon} />}
                    <span className="menu-label">{r.label}</span>
                    {(r.badges || []).map((b) => <span key={b} className="badge">{b}</span>)}
                    {r.word && <span className="menu-word mono">{r.word}</span>}
                    {r.kbd && <Kbd keys={r.kbd} />}
                  </button>
                ))}
              </div>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
