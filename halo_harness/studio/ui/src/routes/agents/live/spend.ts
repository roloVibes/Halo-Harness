// What the drawn work spent (3.4.1.0 R5, live re-check defect 33): the agents' own costs. On the fleet scope a machine,
// a session or a mission part is a node too, and it carries the money its agents spent (a session's spend IS its
// agents'), so summing every node said $0.015 for a member's one `halo -p` session of $0.0075. No imports: tests run it.
export type Costed = { kind?: string; cost: number | null };

export function liveSpend(nodes: Costed[]): number {
  return nodes.reduce((s, n) => s + (n.kind ? 0 : Number(n.cost) || 0), 0);
}
