// A modal on a scrim: glass surface, title, Esc or a scrim click closes it,
// focus moves into it on open and back where it was on close.
import { useEffect, useRef, type ReactNode } from "react";
import { Surface } from "./Surface";
import { Icon } from "./Icon";

type Props = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
  labelledBy?: string;
  footer?: ReactNode;
  /** Above the title: a small mono line (a kicker). */
  kicker?: string;
  testid?: string;
};

export function Dialog({ open, onClose, title, children, className, footer, kicker, testid }: Props) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const first = box.current?.querySelector<HTMLElement>("input, textarea, select, button, [tabindex]");
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      before?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="scrim" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={box} role="dialog" aria-modal="true" aria-label={title} className={"dialog" + (className ? " " + className : "")} data-testid={testid}>
        <Surface className="dialog-surface">
          {title && (
            <header className="dialog-head">
              <div>
                {kicker && <div className="glance-kicker mono">{kicker}</div>}
                <h2 className="dialog-title">{title}</h2>
              </div>
              <button className="icon-btn" onClick={onClose} aria-label="Close" title="Close (Esc)">
                <Icon name="close" />
              </button>
            </header>
          )}
          <div className="dialog-body">{children}</div>
          {footer && <footer className="dialog-foot">{footer}</footer>}
        </Surface>
      </div>
    </div>
  );
}
