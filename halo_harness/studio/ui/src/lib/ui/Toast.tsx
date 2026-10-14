// Toasts rise from the bottom right: `done` sweeps green once, `error`
// flashes red once and keeps a red edge. Driven by `toast()` in lib/store.
import { studio, useStore } from "../store";

export function Toasts() {
  const toasts = useStore(studio, (s) => s.toasts);
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.tone}`} data-motion={t.tone === "info" ? "none" : t.tone} role={t.tone === "error" ? "alert" : "status"}>
          <span className="toast-dot" aria-hidden="true" />
          {t.text}
        </div>
      ))}
    </div>
  );
}
