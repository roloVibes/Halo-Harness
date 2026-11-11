// Hop around, the same habit everywhere: J / K the next / previous live
// agent (Session's map; the Roles canvas, 3.0.7.0 R2: in React, its Live tab
// open on the agent; 3.4.0.0 D: the Orchestra lanes' J / K went with Runs), F follow (the stream scrolls with it),
// Space pins the current stream (its mini
// stream stays on screen), Esc unpins, P pauses or resumes. Inside the agent
// panel K is Stop, with a confirm, so a stray K on the map never stops
// anything. 3.0.6.0 R8: M brings the Mission panel up (3.3.16.0 R2: in Agents,
// Live's Mission panel since 3.4.0.0 D; the Fleet section went, Live hops every machine's agents
// on the fleet scope). Keys typed in a box, with a modifier, or that a panel, a menu
// or a dialog already took, stay where they are. An F nothing here takes
// (and every Shift+F) goes on to Focus (3.3.2.0 R1, shell/keys.ts). 3.3.11.0 R2: in Roles, L switches the
// canvas between Plan and Live, and on Live J / K hop the session tree's working agents.
import { useEffect } from "react";
import { studio } from "../../lib/store";
import { onPart } from "../agents/store";
import { hopCard } from "../roles/live";
import { hopLive } from "../roles/liveModel";
import { roles, setCanvasView } from "../roles/store";
import { askStop, hop, pin, toggleFollow, togglePause } from "./actions";
import { showFleetPanel } from "./extras";
import { fleet } from "./store";

const TYPING = "input, textarea, select, [contenteditable]";
const PRESSABLE = "button, a, [role=button], [role=menuitem], iframe";
export function useHopKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.(TYPING)) return;
      const s = studio.get();
      if (s.paletteOpen || s.help) return;
      const f = fleet.get();
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (key === "f" && e.shiftKey) return; // 3.3.2.0 R1: Shift+F is Focus everywhere (shell/keys.ts useFocusKey)
      if (key === "Escape") {
        if (f.pinned && !f.confirm) {
          e.preventDefault();
          pin("");
        }
        return;
      }
      const dir = key === "j" ? 1 : key === "k" ? -1 : 0;
      if (key === "m" && !e.shiftKey && s.section === "agents") return (e.preventDefault(), showFleetPanel("fleet-mission"));
      if (onPart("roles")) { // Agents on Cast or Live
        const watched = roles.get().watched;
        const real = watched && !watched.startsWith("replay|") ? watched : "";
        if (dir) (roles.get().canvasView === "live" ? hopLive(dir) : hopCard(dir)); // 3.3.11.0 R2: Live hops the tree
        else if (key === "l") setCanvasView(roles.get().canvasView === "live" ? "plan" : "live"); // 3.3.11.0 R2: Plan | Live
        else if (key === " " && real && !t?.closest?.(PRESSABLE)) pin(f.pinned === real ? "" : real);
        else if (key === "p" && real && roles.get().tab === "live") void togglePause(real);
        else if (key === "f" && real && roles.get().tab === "live") toggleFollow();
        else return;
        e.preventDefault();
        return;
      }
      if (s.section !== "session" || f.confirm) return; // 3.1.4.0 R2: Session hops this harness's agents
      const inAgent = !!t?.closest?.('[data-panel="session-agent"]');
      if (key === "j") hop(1);
      else if (key === "k") inAgent ? askStop() : hop(-1);
      else if (key === "f") toggleFollow();
      else if (key === "p") void togglePause();
      else if (key === " " && f.selected && !t?.closest?.(PRESSABLE)) pin(f.pinned === f.selected ? "" : f.selected);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
