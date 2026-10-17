// The framed classic page (Roles at /legacy/?embedded=1; Org and Design are
// React sections since 3.0.7.0 R3) talks
// to the shell with postMessage, same origin only: `{type: "legacy-status",
// mode, text}` is the page's status line, shown in the shell's status bar
// (the page hides its own); `{type: "legacy-section", to}` is the page's
// R / O / D (or Alt+1..6) key, which switches the shell's section instead of
// the frame.
import { useEffect } from "react";
import { goSection, SECTION_IDS, studio, type SectionId } from "../lib/store";

const MODES: SectionId[] = ["roles"];

export function useLegacyMessages(): void {
  useEffect(() => {
    const on = (e: MessageEvent) => {
      if (e.origin !== location.origin || !e.data || typeof e.data !== "object") return;
      const d = e.data as { type?: unknown; mode?: unknown; to?: unknown; text?: unknown };
      if (d.type === "legacy-status" && MODES.includes(d.mode as SectionId) && typeof d.text === "string") {
        const mode = d.mode as SectionId;
        const text = d.text.slice(0, 400);
        studio.update((s) => (s.legacy[mode] === text ? {} : { legacy: { ...s.legacy, [mode]: text } }));
      } else if (d.type === "legacy-section" && SECTION_IDS.includes(d.to as SectionId)) {
        goSection(d.to as SectionId);
      }
    };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);
}
