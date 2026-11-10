// Session's timeline "by group" (3.3.16.3): the lanes in the same groups Live boxes (groups.ts) -- the lanes of agents in
// no group first, then each group's title row and its lanes, in the order the groups started. Pure.
import { recordOf } from "../../../lib/work/record";
import type { Harness, SessionRow } from "../../fleet/types";
import type { LiveNode } from "../../roles/liveModel";
import { withGroups, type GroupTag } from "./groups";

type Lane = { key: string; h: Harness; s: SessionRow };
export type LaneRow<R> = { head: GroupTag; n: number; r?: undefined } | { r: R; head?: undefined; n?: undefined };

/** The box tag of every agent key of one session (none for an agent in no box). */
function tagsOf(h: Harness, s: SessionRow): Map<string, GroupTag> {
  const rec = recordOf(h, s);
  const nodes = rec.agents.map((a) => ({ id: a.id, key: a.key, parent: a.orphan ? null : a.parent, name: a.name, role: a.role, model: a.model,
                                         state: a.state, card: "" }) as LiveNode);
  const out = new Map<string, GroupTag>();
  for (const n of withGroups(nodes, rec)) if (n.group && n.group.kind !== "tier") out.set(n.key, n.group);
  return out;
}

export function byGroup<R extends Lane>(live: R[], on = true): LaneRow<R>[] {
  if (!on) return live.map((r) => ({ r }));
  const tags = new Map<string, GroupTag>();
  const seen = new Set<string>();
  for (const r of live) {
    const sk = `${r.h.id}|${r.s.session_id}`;
    if (seen.has(sk)) continue;
    seen.add(sk);
    for (const [k, g] of tagsOf(r.h, r.s)) tags.set(k, g);
  }
  const loose = live.filter((r) => !tags.has(r.key));
  const groups = new Map<string, R[]>();
  for (const r of live) if (tags.has(r.key)) groups.set(tags.get(r.key)!.id, [...(groups.get(tags.get(r.key)!.id) || []), r]);
  const out: LaneRow<R>[] = loose.map((r) => ({ r }));
  for (const [, rs] of groups) out.push({ head: tags.get(rs[0].key)!, n: rs.length }, ...rs.map((r) => ({ r })));
  return out;
}
