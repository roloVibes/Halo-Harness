// What a lit box adds (3.6.0.0 R4, the design's "each box's state (working / waiting / done), what it does now and its
// cost"): a row per fact, so the box grows and nothing is cut -- its state, what it does now in a few words, its cost
// so far. A helper the session made up says so ("made up for this task"), its task, and offers **Save as an agent**:
// POST crew/from-live builds an unsaved agent body from it and the Agents form opens with it; nothing is written until
// Save there. An opened workflow box lists its steps lit as the step runner reports them (the agents in a step, a
// repeat's rounds and checks). 3.6.0.0 R4b: the seconds on "what it does now" (useClock); a helper that started helpers
// says "+N under it" (a click lists them in the drawer).
import { api, ApiError } from "../../../lib/api";
import { toast, useStore } from "../../../lib/store";
import { secsWords } from "../live/waits";
import { waitStore } from "../live/useWaits";
import { cost as money } from "../../orchestra/format";
import { setAgentsView } from "../../agents/store";
import { fillFromLive } from "../store";
import type { Agent } from "../types";
import { under, type BoxState, type Helper, type OvBox, type Steps } from "./overlay";
import { openFeed } from "./feedOpen";

export const STATE_WORDS: Record<BoxState, string> = { working: "working", waiting: "waiting on you", done: "done", failed: "failed", idle: "not used yet" };

/** R4b (R4's gap 6): how long the box's agent has been at what it does now ("12 s"), from the waits Live's nodes use
 *  (agents/live/waits.ts, computed for the top line's sentence): its tool's start, its ask's, its last line's. */
export function useClock(ids: string[], now: number): string {
  const since = useStore(waitStore, (s) => ids.map((id) => s.waits[id]?.since || 0).find(Boolean) || 0);
  return since ? secsWords(since, now * 1000) : "";
}

export function LitRows({ ob, now }: { ob: OvBox; now: number }) {
  const clock = useClock(ob.state === "working" || ob.state === "waiting" ? ob.agents : [], now);
  const doing = ob.state === "waiting" ? STATE_WORDS.waiting : ob.doing;
  return (
    <span className="mp-lit" data-testid="map-lit">
      <span className="mp-lit-row mono" data-testid="map-lit-state" data-state={ob.state}>{STATE_WORDS[ob.state]}</span>
      {ob.state !== "idle" && (ob.doing !== STATE_WORDS[ob.state] || clock) && (
        <span className="mp-lit-row" data-testid="map-lit-doing" data-clock={clock || undefined}>{doing}{clock ? ` · ${clock}` : ""}</span>
      )}
      {ob.cost > 0 && <span className="mp-lit-row mono mp-muted" data-testid="map-lit-cost">{money(ob.cost)} so far</span>}
    </span>
  );
}

export async function saveAsAgent(sid: string, aid: string): Promise<boolean> {
  try {
    const r = await api.post<{ agent: Agent; from: { name?: string } }>("crew/from-live", { session: sid, agent_id: aid });
    fillFromLive(r.agent, String(r.from?.name || aid));
    setAgentsView("crew");
    return true;
  } catch (e) {
    toast(`Save as an agent: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  }
}

export function HelperRows({ h, sid, all }: { h: Helper; sid: string; all: Helper[] }) {
  const below = under(all, h.aid);
  return (
    <span className="mp-lit" data-testid="map-helper-rows">
      <span className="mp-tag mp-made" data-testid="map-made-up">made up for this task</span>
      {h.task && <span className="mp-lit-row" data-testid="map-helper-task">{h.task.length > 140 ? h.task.slice(0, 137) + "..." : h.task}</span>}
      <span className="mp-lit-row mono" data-state={h.state}>{STATE_WORDS[h.state]}{h.cost > 0 ? ` · ${money(h.cost)}` : ""}</span>
      {below.length > 0 && ( // R4b (R4's gap 2): the helpers it started, listed in the drawer, not drawn
        <button type="button" className="mp-link" data-testid="map-helper-under" data-n={below.length} title="List them in the drawer: who started whom"
                onClick={(e) => { e.stopPropagation(); openFeed(`under:${h.aid}`); }}>+{below.length} under it</button>
      )}
      {sid && (
        <button type="button" className="mp-link" data-testid="map-save-agent" title="Open the Agents form with an agent built from this helper; nothing is saved until you press Save there"
                onClick={(e) => { e.stopPropagation(); void saveAsAgent(sid, h.aid); }}>
          Save as an agent
        </button>
      )}
    </span>
  );
}

const STEP_WORDS: Record<string, string> = { running: "running", done: "done", waiting: "not yet", skipped: "skipped", failed: "failed", capped: "stopped at the cap", stopped: "stopped" };

export function LitSteps({ steps }: { steps: Steps }) {
  return (
    <span className="mp-lit" data-testid="map-lit-steps" data-state={steps.state}>
      {steps.steps.map((s) => (
        <span key={s.n} className="mp-step" data-testid="map-lit-step" data-state={s.state}>
          {s.n} · {s.name}: {STEP_WORDS[s.state] || s.state}
          {s.agents.length > 0 && <span className="mp-muted"> ({s.agents.join(" + ")})</span>}
          {s.checks > 0 && <span className="mp-muted"> · repeat: round {Math.max(s.rounds, 1)}, {s.checks} check{s.checks === 1 ? "" : "s"}</span>}
        </span>
      ))}
    </span>
  );
}
