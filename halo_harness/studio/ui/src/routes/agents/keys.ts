// Agents' view keys (3.3.16.0 R1): C Cast, R Runs, L Live, while Agents is on screen and the key is not typed into a
// field, a dialog or the palette. L on Live goes back to Cast (Roles' L toggled Plan | Live, and still does: the
// shell's hop keys, routes/fleet/hop.ts, may take it first; either way it toggles).
import { useEffect } from "react";
import { studio } from "../../lib/store";
import type { AgentsView } from "../../lib/agentsDoor";
import { agentsView, setAgentsView } from "./store";

const TYPING = "input, textarea, select, [contenteditable]";
const KEYS: Record<string, AgentsView> = { c: "cast", r: "runs", l: "live", w: "workflows" }; // 3.3.16.0 R3: W the board

export function useAgentsKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.repeat) return;
      const view = KEYS[e.key.toLowerCase()];
      const s = studio.get();
      if (!view || s.section !== "agents" || s.paletteOpen || s.help) return;
      if ((e.target as HTMLElement | null)?.closest?.(TYPING) || document.querySelector("[role=dialog]")) return;
      e.preventDefault();
      setAgentsView(view === "live" && agentsView() === "live" ? "cast" : view);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
