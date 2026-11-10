// The fleet's Attention queue in Agents (3.3.16.0 R2 "the Fleet fold": Fleet's Attention panel; "amber = waits on
// you"): one chip on Agents' bar in every view, **Attention · N**, amber while N > 0, and the queue as a panel over the
// view (`fleet-attention`, the panel id it always had), closed on load -- the chip, `A` on Agents (outside a text box and
// outside the panel itself, where A answers the selected row) and the palette's "Agents: Attention" toggle it. Each row
// keeps its one-key answers; `o` opens the right view. Not remembered: every load starts with it closed.
import { useEffect } from "react";
import { createStore, studio, useStore } from "../../lib/store";

const open = createStore<{ on: boolean }>({ on: false });

export const useAttentionOpen = (): boolean => useStore(open, (s) => s.on);

export function setAttention(on: boolean): void {
  open.update((s) => (s.on === on ? {} : { on }));
}

export function toggleAttention(): void {
  setAttention(!open.get().on);
}

const TYPING = "input, textarea, select, [contenteditable]";

/** `A` on Agents toggles the queue (the panel's own A, answering a row, takes it first while the focus is in it). */
export function useAttentionKey(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.repeat || e.key.toLowerCase() !== "a") return;
      const s = studio.get();
      const t = e.target as HTMLElement | null;
      if (s.section !== "agents" || s.paletteOpen || s.help || t?.closest?.(TYPING) || t?.closest?.('[data-panel="fleet-attention"]')) return;
      if (document.querySelector("[role=dialog]")) return;
      e.preventDefault();
      toggleAttention();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
