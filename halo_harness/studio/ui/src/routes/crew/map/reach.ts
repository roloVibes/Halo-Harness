// Which boxes a session can ever run (3.6.0.2 R45, for Session's drawing top to bottom only): the boxes a chain of lines
// from main reaches. The others wait below the last rank under "Not connected yet", including a box fed only by another
// unconnected box (Agents -> Map's strip is view()'s own split and stays as it is).
import type { DrawBox, DrawLine } from "./mapTypes";

/** Every box id a chain of lines from `from` reaches, `from` included. */
export function reach(lines: Pick<DrawLine, "from" | "to">[], from = "main"): Set<string> {
  const seen = new Set<string>([from]);
  const todo = [from];
  while (todo.length) {
    const at = todo.shift()!;
    for (const l of lines) if (l.from === at && !seen.has(l.to)) {
      seen.add(l.to);
      todo.push(l.to);
    }
  }
  return seen;
}

/** view()'s boxes and strip split again by reach from main, input order kept (boxes first, then the strip). */
export function split(boxes: DrawBox[], strip: DrawBox[], lines: Pick<DrawLine, "from" | "to">[]): { reached: DrawBox[]; unreached: DrawBox[] } {
  const on = reach(lines);
  const all = [...boxes, ...strip];
  return { reached: all.filter((b) => b.main || on.has(b.id)), unreached: all.filter((b) => !b.main && !on.has(b.id)) };
}
