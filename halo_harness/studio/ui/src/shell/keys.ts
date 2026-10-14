// Global keys: Alt+1..4 switch sections, Ctrl/Cmd+K toggles the palette, Esc
// closes the palette, then the Inspector. (Keys typed inside a framed legacy
// page stay with that page.)
import { useEffect } from "react";
import { goSection, studio } from "../lib/store";
import { SECTIONS } from "../routes";

export function useGlobalKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && !e.altKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        studio.update((s) => ({ paletteOpen: !s.paletteOpen }));
        return;
      }
      if (e.altKey && !mod && !e.shiftKey && /^Digit[1-4]$/.test(e.code)) {
        e.preventDefault();
        goSection(SECTIONS[Number(e.code.slice(5)) - 1].id);
        return;
      }
      if (e.key === "Escape") {
        const s = studio.get();
        if (s.paletteOpen) studio.update(() => ({ paletteOpen: false }));
        else if (s.inspector) studio.update(() => ({ inspector: null }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
