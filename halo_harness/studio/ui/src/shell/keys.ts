// Global keys: Alt+1..8 switch sections in the registry's order (routes/index.tsx SECTIONS; 3.1.6.0 R6:
// Session Alt+1 ... Orchestra Alt+6; 3.2.0.0 R6: Packs Alt+7; 3.3.0.0 R1: Setup Alt+8, then Alt+9 a pack's own section), Ctrl/Cmd+K toggles the palette,
// `?` (Shift+/) opens "How this works" for the section (a focused panel
// takes `?` first for its own help), Esc closes the palette, then the
// Inspector. A key a panel, a menu or a dialog already handled (its default
// prevented) stops there. 3.3.2.0 R1: F toggles Focus (useFocusKey, after the
// hop keys: where F already follows an agent or the Log, or fits the Roles
// canvas, that F wins and Shift+F is Focus).
import { useEffect } from "react";
import { closeHelp, goSection, openHelp, studio, toggleFocus } from "../lib/store";
import { sections } from "../routes";

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
      const def = e.altKey && !mod && !e.shiftKey && /^Digit[1-9]$/.test(e.code) ? sections()[Number(e.code.slice(5)) - 1] : undefined;
      if (def && def.kbd) {
        e.preventDefault();
        goSection(def.id);
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

/** 3.3.2.0 R1: F (or Shift+F) outside a text field, with nothing open over the page, toggles Focus. App registers
 *  it after the hop keys (routes/fleet/hop.ts), so an F a section already uses is taken there first. */
export function useFocusKey(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      if (e.key !== "f" && e.key !== "F") return;
      if ((e.target as HTMLElement | null)?.closest?.(TYPING)) return;
      const s = studio.get();
      if (s.paletteOpen || s.help || document.querySelector("[role=dialog]")) return;
      e.preventDefault();
      toggleFocus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
