// Agents' Attention chip and its panel (3.3.16.0 R2 "the Fleet fold"; attention.ts says what they are). The chip
// counts the fleet's queue (every harness: Agents never narrows it to one, Session's own pending dock does that for
// this session) and is amber while anything waits; a new row blinks it once (the Instrument's one blink: `data-blink`,
// keyed by the newest row). The panel floats over the view's top right under the bar, Fleet's Attention as it was
// (AttentionDetail: oldest first, J / K, A / R / S / O on the selected row), and closes with its x or Esc.
import { useEffect, useRef, useState } from "react";
import { Icon } from "../../lib/ui";
import { AttentionDetail } from "../fleet/Attention";
import { useAttnCount, usePanels } from "../fleet/pstore";
import { useCounts } from "../fleet/store";
import { startFleet } from "../fleet/sync";
import { setAttention, toggleAttention, useAttentionOpen } from "./attention";

export function AttentionChip() {
  useEffect(() => startFleet(), []);
  const c = useCounts();
  const n = useAttnCount(c.attention);
  const on = useAttentionOpen();
  const newest = usePanels((s) => s.attention[s.attention.length - 1]?.id || "");
  const seen = useRef(newest);
  const [blink, setBlink] = useState(false);
  useEffect(() => {
    if (!newest || newest === seen.current) return;
    seen.current = newest;
    setBlink(true);
    const id = window.setTimeout(() => setBlink(false), 900);
    return () => window.clearTimeout(id);
  }, [newest]);
  return (
    <button className="ag-attn-chip mono" data-testid="agents-attention" data-count={n} data-tone={n ? "warn" : undefined} data-blink={blink || undefined}
            aria-pressed={on} onClick={toggleAttention} title={n ? `${n} decision${n === 1 ? "" : "s"} wait on you across the fleet (A)` : "Nothing waits on you (A opens the queue)"}>
      <span className="ag-attn-dot" aria-hidden="true" />
      Attention · {n}
    </button>
  );
}

export function AttentionPanel() {
  const on = useAttentionOpen();
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!on) return;
    box.current?.focus({ preventScroll: true });
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || !box.current?.contains(document.activeElement)) return;
      e.preventDefault();
      setAttention(false);
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [on]);
  if (!on) return null;
  return (
    <section ref={box} className="panel glass ag-attn-panel" data-panel="fleet-attention" data-testid="fleet-attention" tabIndex={-1} aria-label="Attention">
      <header className="panel-head ag-attn-head" data-density="bar">
        <span className="panel-title">Attention</span>
        <span className="mono muted">every decision that waits on you, across the fleet</span>
        <span className="spacer" />
        <button className="icon-btn" onClick={() => setAttention(false)} aria-label="Close" title="Close (Esc, A)" data-testid="agents-attention-close"><Icon name="close" /></button>
      </header>
      <div className="panel-body ag-attn-body" data-density="body">
        <AttentionDetail />
      </div>
    </section>
  );
}
