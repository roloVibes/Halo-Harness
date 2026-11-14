// 3.6.0.0 R1: an Attention row's "open" for a Try it run (live/crew_attention.py): its agent in the form (yours, else
// the project's) and the run's result under Try it, where seeing it marks it seen.
import { crew, openAgent } from "./store";
import { showTry } from "./tryStore";

export async function openCrewTry(agent: string, tryId: string): Promise<void> {
  const row = crew.get().agents.find((a) => a.name === agent);
  await openAgent(agent, row?.scope);
  if (tryId) await showTry(tryId);
}
