// The session's todo plan (3.6.0.0 R4b; 3.6.0.23 PV: ONE path): main's agent row's `plan` (agent/agent_observe.py:
// his last successful TodoWrite list), read from the fleet store, so it is there after a reload and for any session the
// page knows. The Map's top line says "plan: 3 of 7 done" (LitLine.tsx), the Feed's plan filter lists it (FeedParts.tsx
// PlanList), Session's head shows it (session/FeedPlan.tsx). The words are planWords.ts (pure).
import { findSession, localId, useFleet } from "../../fleet/store";
import { countOf, planOf, planWords, type Todo } from "./planWords";

export type { Todo };
export { planWords } from "./planWords";

/** Main's plan of session `sid` on this harness ([] with none). */
export const useTodos = (sid: string): Todo[] => useFleet((s) => planOf(sid ? findSession(s, localId(s), sid)?.s : null));
/** The Map's top line of session `sid`: "plan: 3 of 7 done" over the WHOLE list (the row's `plan_count`), "" with none. */
export const usePlanLine = (sid: string): string => useFleet((s) => {
  const ss = sid ? findSession(s, localId(s), sid)?.s : null;
  return planWords(planOf(ss), countOf(ss));
});
