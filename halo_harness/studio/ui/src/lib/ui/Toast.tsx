// Toasts sit at the top right under the header (3.3.5.0 R0 (h): never over a
// page's foot, Setup's Back / Next). Driven by `toast()` in lib/store. A paged
// section (Setup, Settings) raises none: a block's result is its own line.
// 3.3.15.0 L1, the Instrument look: 300 px, surface-2, one line in mono; one
// arrives with a 16 px rise and fade over 220 ms, holds 4 s and leaves with a
// 180 ms fade (a toast the store dropped stays here, `data-leaving`, for that
// fade); an error keeps its red square and stays until its ✕ dismisses it.
import { useEffect, useRef, useState } from "react";
import { studio, useStore, type ToastItem } from "../store";

const LEAVE_MS = 180;

export function Toasts() {
  const toasts = useStore(studio, (s) => s.toasts);
  const prev = useRef<ToastItem[]>(toasts);
  const [leaving, setLeaving] = useState<ToastItem[]>([]);
  useEffect(() => {
    const gone = prev.current.filter((t) => !toasts.some((n) => n.id === t.id));
    prev.current = toasts;
    if (!gone.length) return;
    setLeaving((l) => [...l, ...gone]);
    const id = window.setTimeout(() => setLeaving((l) => l.filter((t) => !gone.includes(t))), LEAVE_MS);
    return () => window.clearTimeout(id);
  }, [toasts]);
  const dismiss = (id: number) => studio.update((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  const shown = [...toasts.map((t) => ({ t, out: false })), ...leaving.map((t) => ({ t, out: true }))];
  return (
    <div className="toasts" aria-live="polite">
      {shown.map(({ t, out }) => (
        <div key={t.id} className={`toast toast-${t.tone}`} data-tone={t.tone} data-leaving={out || undefined}
             role={t.tone === "error" ? "alert" : "status"}>
          <span className="toast-dot" aria-hidden="true" />
          <span className="toast-text">{t.text}</span>
          {t.tone === "error" && !out && (
            <button className="icon-btn" onClick={() => dismiss(t.id)} aria-label="Dismiss" title="Dismiss" data-testid="toast-dismiss">✕</button>
          )}
        </div>
      ))}
    </div>
  );
}
