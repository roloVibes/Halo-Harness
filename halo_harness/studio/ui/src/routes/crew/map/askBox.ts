// The door of an ask lands on the run's drawing (P4 batch 9, the owner's point 20): an attention alert's Open or a row's O
// (routes/glance/openAsk.ts) names the drawing -- Session's Live drawer or Agents -> 4 · Live -- the session and the
// asking agent; that drawing, once it shows the session with the agent's box drawn, opens the step-in card on that box
// as a click on it does (R18: stepInTarget.ts `stepIn`, runFrame.ts `useStepCard`; no second selection), the asking
// agent's row first so its ask's choices, Pause, Stop and Steer are there (StepInAsk.tsx). The box a card is open on
// carries the selected mark (`data-selected`, runFrame.ts `selected`); a box that waits on him already says so
// (`data-state="waiting"`, P3).
import { useEffect, type RefObject } from "react";
import { createStore, useStore } from "../../../lib/store";
import type { Lit } from "./LitMini";
import { placeOf, stepIn, who, type Hit, type Target } from "./stepInTarget";

export type AskWhere = "session" | "live";
type Want = { where: AskWhere | ""; sid: string; aid: string; n: number };
const NONE: Want = { where: "", sid: "", aid: "", n: 0 };
const want = createStore<Want>(NONE);

/** Ask drawing `where` to open the card of agent `aid` of session `sid` (the last ask wins). */
export function askBox(where: AskWhere, sid: string, aid: string): void {
  want.update((s) => ({ where, sid, aid: aid || "main", n: s.n + 1 }));
}

/** The card a click on `el` opens, with the asking agent's row first (it may not be live by the rows' reading). */
export function askTarget(el: HTMLElement, aid: string, L: Pick<Lit, "agents" | "ov">): Target {
  const face = el.querySelector<HTMLElement>(el.dataset.workflow ? "[data-testid=session-map-block-head]" : ".mp-lit-row");
  const text = face?.textContent || "";
  const h: Hit = el.dataset.workflow ? { kind: "head", workflow: el.dataset.workflow, text }
    : { kind: "box", box: el.dataset.box || "", name: el.querySelector(".mp-name")?.textContent || el.dataset.box || "", text };
  const t = stepIn(h, L.agents, L.ov);
  const me = L.agents.find((a) => a.id === aid);
  return me ? { ...t, title: who(me).name, who: [who(me), ...t.who.filter((w) => w.aid !== aid)] } : t;
}

/** In a run's drawing: when the door asked for this drawing and session, open the card on the asking agent's box once it
 *  is drawn (until then every draw looks again). */
export function useAskedBox(where: AskWhere, sid: string, L: Lit, world: RefObject<HTMLElement | null>, setCard: (t: Target) => void): void {
  const w = useStore(want, (s) => s);
  useEffect(() => {
    if (!w.n || w.where !== where || w.sid !== sid) return;
    const at = placeOf(w.aid, L.ov, L.agents);
    const sel = at?.box ? `[data-box="${CSS.escape(at.box)}"]` : at?.workflow ? `[data-workflow="${CSS.escape(at.workflow)}"]` : "";
    const el = sel ? world.current?.querySelector<HTMLElement>(sel) : null;
    if (!el) return; // not drawn yet: the next draw looks again
    want.update(() => NONE);
    setCard(askTarget(el, w.aid, L));
    el.scrollIntoView({ block: "nearest", inline: "nearest" });
  });
}
