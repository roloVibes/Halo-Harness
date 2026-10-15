// Hop around, the same habit everywhere: J / K the next / previous live
// agent (the Fleet map; the Roles and Org canvases, where the framed page
// does the hop; the Orchestra lanes), F follow (the stream scrolls with it;
// Orchestra: the Log follows), Space pins the current stream (its mini
// stream stays on screen), Esc unpins, P pauses or resumes. Inside the agent
// panel K is Stop, with a confirm, so a stray K on the map never stops
// anything. 3.0.6.0 R8: M (in Fleet) brings the Mission panel up and focuses
// it. Keys typed in a box, with a modifier, or that a panel, a menu
// or a dialog already took, stay where they are.
import { useEffect } from "react";
import { studio } from "../../lib/store";
import { focusLane, orch, setOpt } from "../orchestra/store";
import { askStop, hop, pin, toggleFollow, togglePause } from "./actions";
import { showFleetPanel } from "./extras";
import { fleet } from "./store";

const TYPING = "input, textarea, select, [contenteditable]";
const PRESSABLE = "button, a, [role=button], [role=menuitem], iframe";
const LIVE_LANES = ["writing", "in_review", "waiting"];

/** J / K on the Orchestra lanes: the next lane at work (every lane when none is). */
function hopLane(dir: 1 | -1): void {
  const lanes = orch.get().data?.lanes || [];
  const live = lanes.filter((l) => LIVE_LANES.includes(l.state));
  const list = (live.length ? live : lanes).map((l) => l.lane);
  if (!list.length) return;
  const i = list.indexOf(orch.get().focusLane ?? -1);
  focusLane(list[i < 0 ? (dir > 0 ? 0 : list.length - 1) : (i + dir + list.length) % list.length]);
}

/** J / K on a framed canvas: the page itself hops across its cards (static/legacy/live.js). */
function frameHop(section: string, dir: 1 | -1): void {
  const frame = document.querySelector<HTMLIFrameElement>(`.section-view[data-section="${section}"] iframe.legacy-frame`);
  frame?.contentWindow?.postMessage({ type: "fleet-hop", dir }, location.origin);
}

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
      if (key === "Escape") {
        if (f.pinned && !f.confirm && !f.pairOpen) {
          e.preventDefault();
          pin("");
        }
        return;
      }
      const dir = key === "j" ? 1 : key === "k" ? -1 : 0;
      if (s.section === "orchestra") {
        if (dir) (e.preventDefault(), hopLane(dir));
        else if (key === "f") (e.preventDefault(), setOpt("follow", !orch.get().opts.follow));
        return;
      }
      if (s.section === "roles" || s.section === "org") {
        if (dir) (e.preventDefault(), frameHop(s.section, dir));
        return;
      }
      if (s.section !== "fleet" || f.confirm) return;
      const inAgent = !!t?.closest?.('[data-panel="fleet-agent"]');
      if (key === "j") hop(1);
      else if (key === "k") inAgent ? askStop() : hop(-1);
      else if (key === "f") toggleFollow();
      else if (key === "p") void togglePause();
      else if (key === "m") showFleetPanel("fleet-mission");
      else if (key === " " && f.selected && !t?.closest?.(PRESSABLE)) pin(f.pinned === f.selected ? "" : f.selected);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
