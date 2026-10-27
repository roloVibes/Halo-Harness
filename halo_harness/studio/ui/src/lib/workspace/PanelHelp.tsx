// A panel's help: a small popover under its title bar with the `about`
// line and the `help` lines of its PanelSpec, opened by the ? on its title
// line (3.3.2.0 R3: the about line's only place on the panel), from the ...
// menu or with `?` while the panel is focused. Esc or a click outside closes it;
// `?` again opens the section's "How this works" (the Panel handles keys).
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../ui/Icon";
import { Kbd } from "../ui/Kbd";
import type { PanelSpec } from "./types";

const W = 344;

type Props = { spec: PanelSpec; anchor: RefObject<HTMLElement | null>; sectionTitle: string; onClose: () => void };

export function PanelHelp({ spec, anchor, sectionTitle, onClose }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: -9999, top: 0 });

  useLayoutEffect(() => {
    const place = () => {
      const r = anchor.current?.getBoundingClientRect();
      if (!r) return;
      setPos({ left: Math.max(8, Math.min(r.right - W - 8, window.innerWidth - W - 8)), top: Math.max(8, Math.min(r.top + 42, window.innerHeight - 280)) });
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [anchor]);

  useEffect(() => {
    const off = (e: PointerEvent) => {
      const t = e.target as Node;
      const toggle = anchor.current?.querySelector("[data-testid=panel-help-btn]"); // its own ? toggles it
      if (!box.current?.contains(t) && !toggle?.contains(t)) onClose();
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("pointerdown", off, true);
    window.addEventListener("keydown", esc, true);
    return () => {
      window.removeEventListener("pointerdown", off, true);
      window.removeEventListener("keydown", esc, true);
    };
  }, [onClose, anchor]);

  const lines = (spec.help || "").split("\n").filter(Boolean);
  return createPortal(
    <div ref={box} className="panel-help glass" role="dialog" aria-label={`${spec.title}: how to use it`} style={{ left: pos.left, top: pos.top, width: W }} data-testid="panel-help">
      <header className="panel-help-head">
        <span className="glance-kicker mono">HOW TO USE</span>
        <b className="panel-help-title">{spec.title}</b>
        <button className="icon-btn" onClick={onClose} aria-label="Close the help" title="Close (Esc)">
          <Icon name="close" />
        </button>
      </header>
      {spec.about && <p className="panel-help-about">{spec.about}</p>}
      {lines.length > 0 && (
        <ul className="panel-help-lines">
          {lines.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      <footer className="panel-help-foot mono">
        <span>
          <Kbd keys="Alt+Arrows" /> move · <Kbd keys="Alt+Shift+Arrows" /> resize
        </span>
        <span>
          <Kbd keys="?" /> again: how {sectionTitle} works · <Kbd keys="Esc" /> close
        </span>
      </footer>
    </div>,
    document.body,
  );
}
