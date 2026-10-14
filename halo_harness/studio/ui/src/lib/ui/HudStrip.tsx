// The status-bar strip: mono cells separated by thin rules. `HudCell` is one
// cell with an optional small caps label.
import type { ReactNode } from "react";

export function HudStrip({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <footer className="hud-strip" role="status" aria-label={label}>
      {children}
    </footer>
  );
}

export function HudCell({ label, children, grow, title }: { label?: string; children: ReactNode; grow?: boolean; title?: string }) {
  return (
    <div className={"hud-cell" + (grow ? " hud-grow" : "")} title={title}>
      {label && <span className="hud-label">{label}</span>}
      <span className="hud-value">{children}</span>
    </div>
  );
}
