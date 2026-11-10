// What a mission part's edge and node say (3.0.9.0; 3.3.16.0 R2: out of the Fleet Map's MapMission.tsx when the Map
// went -- Live's part nodes and Runs' plan table read them): what a depends_on edge carries, and where a repo part
// starts.
import type { PlanPart, View } from "./mstore";

/** What a depends_on edge carries: `all`, the dependency's outputs, or its hand-back. */
export function handoffLabel(v: View, part: PlanPart, dep: string): string {
  if (part.take === "all") return "all";
  const d = v.plan?.parts.find((x) => x.id === dep);
  const names = (d?.outputs || []).map((o) => o.split("/").pop() || o);
  return names.length ? names.join(", ") : "hand-back";
}

/** Where a repo part starts: its run's base, its repo dependencies' head, or the mission's base. */
export function partBase(v: View, p: PlanPart): string {
  if (p.kind !== "repo") return "";
  const run = v.mission.parts?.[p.id];
  if (run?.base) return `base ${run.base.slice(0, 7)}`;
  const deps = p.depends_on.filter((d) => v.plan?.parts.find((x) => x.id === d)?.kind === "repo");
  if (deps.length) return `base: ${deps.join("+")}'s head`;
  return v.mission.repo?.base ? `base ${v.mission.repo.base.slice(0, 7)}` : "";
}
