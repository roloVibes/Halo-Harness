// A modal on a scrim: the panel frame with its corner ticks, the title in mono
// caps, Esc or a scrim click closes it, focus moves into it on open and back
// where it was on close. 3.3.15.0 L1, the Instrument look: 480 px, the one
// shadow level, and on a confirmation (`cost`) the three mono lines DOES /
// COSTS / WRITES before the buttons (lib/ui/DialogCost.tsx).
import { useEffect, useRef, type ReactNode } from "react";
import { Surface } from "./Surface";
import { Icon } from "./Icon";
import { DialogCost, type DialogCostLines } from "./DialogCost";

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
  /** A confirmation: what pressing its button does, what it costs and what it writes. */
  cost?: DialogCostLines;
};

export function Dialog({ open, onClose, title, children, className, footer, kicker, testid, cost }: Props) {
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
          {cost && <DialogCost cost={cost} />}
          {footer && <footer className="dialog-foot">{footer}</footer>}
        </Surface>
      </div>
    </div>
  );
}
