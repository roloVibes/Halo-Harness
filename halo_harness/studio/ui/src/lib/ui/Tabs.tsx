// Tabs with a sliding indicator under the active one. Each item may carry a
// keyboard hint, a state motion and a data-testid.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { MotionState } from "../motion";
import { Kbd } from "./Kbd";

export type TabItem = { id: string; label: ReactNode; kbd?: string; motion?: MotionState; testid?: string; title?: string };

export function Tabs({ items, value, onChange, label }: { items: TabItem[]; value: string; onChange: (id: string) => void; label: string }) {
  const row = useRef<HTMLDivElement>(null);
  const [bar, setBar] = useState({ left: 0, width: 0 });
  useLayoutEffect(() => {
    const measure = () => {
      const el = row.current?.querySelector<HTMLElement>(`[data-tab-id="${value}"]`);
      if (el) setBar({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (row.current) ro.observe(row.current);
    return () => ro.disconnect();
  }, [value, items.length]);
  return (
    <div className="tabs" role="tablist" aria-label={label} ref={row}>
      {items.map((it) => (
        <button
          key={it.id}
          role="tab"
          aria-selected={it.id === value}
          className={"tab" + (it.id === value ? " on" : "")}
          data-tab-id={it.id}
          data-testid={it.testid}
          data-motion={it.motion ?? "none"}
          title={it.title}
          onClick={() => onChange(it.id)}
        >
          <span className="tab-label">{it.label}</span>
          {it.kbd && <Kbd keys={it.kbd} className="tab-kbd" />}
        </button>
      ))}
      <span className="tab-indicator" style={{ transform: `translateX(${bar.left}px)`, width: bar.width }} aria-hidden="true" />
    </div>
  );
}
