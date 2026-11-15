// Agents' tab keys (3.6.0.0 R5): 1 · Agents, 2 · Workflows, 3 · Map, while Agents is on screen and the key is not typed
// into a field, a dialog or the palette. For this release the old keys still land: C (Cast) and L (Live) on the Map,
// W (the board) on Workflows.
import { useEffect } from "react";
import { studio } from "../../lib/store";
import type { AgentsView } from "../../lib/agentsDoor";
import { setAgentsView } from "./store";

const TYPING = "input, textarea, select, [contenteditable]";
const KEYS: Record<string, AgentsView> = { "1": "crew", "2": "workflows", "3": "map", c: "map", l: "map", w: "workflows" };

export function useAgentsKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.repeat) return;
      const view = KEYS[e.key.toLowerCase()];
      const s = studio.get();
      if (!view || s.section !== "agents" || s.paletteOpen || s.help) return;
      if ((e.target as HTMLElement | null)?.closest?.(TYPING) || document.querySelector("[role=dialog]")) return;
      e.preventDefault();
      setAgentsView(view);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
