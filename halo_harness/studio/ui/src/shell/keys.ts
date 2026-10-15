// Global keys: Alt+1..6 switch sections, Ctrl/Cmd+K toggles the palette,
// `?` (Shift+/) opens "How this works" for the section (a focused panel
// takes `?` first for its own help), Esc closes the palette, then the
// Inspector. A key a panel, a menu or a dialog already handled (its default
// prevented) stops there. (Keys typed inside a framed legacy page stay with
// that page.)
import { useEffect } from "react";
import { closeHelp, goSection, openHelp, studio } from "../lib/store";
import { SECTIONS } from "../routes";

const TYPING = "input, textarea, select, [contenteditable]";

export function useGlobalKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && !e.altKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        studio.update((s) => ({ paletteOpen: !s.paletteOpen }));
        return;
      }
      if (e.altKey && !mod && !e.shiftKey && /^Digit[1-6]$/.test(e.code)) {
        e.preventDefault();
        goSection(SECTIONS[Number(e.code.slice(5)) - 1].id);
        return;
      }
      const typing = (e.target as HTMLElement | null)?.closest?.(TYPING);
      if (e.key === "?" && !mod && !e.altKey && !typing) {
        e.preventDefault();
        const s = studio.get();
        if (s.help) closeHelp();
        else openHelp(s.section);
        return;
      }
      if (e.key === "Escape") {
        const s = studio.get();
        // what Esc closed is taken: the Fleet hop keys (Esc unpins the mini stream) leave it alone
        if (s.paletteOpen) (e.preventDefault(), studio.update(() => ({ paletteOpen: false })));
        else if (s.inspector) (e.preventDefault(), studio.update(() => ({ inspector: null })));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
