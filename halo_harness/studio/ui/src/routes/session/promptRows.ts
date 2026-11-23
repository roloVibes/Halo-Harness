// The Prompt panel's rows (split from PromptFeed.tsx in 3.6.0.11 so node can run it: `import type` only). Your turns, the
// main agent's lines the panel shows and the slash outputs, oldest first. 3.6.0.11 (reader E): a prompt the panel did
// not hear as a `user_message` (typed before Studio attached: the backlog's `asked` line of main) is a turn too, so an
// answer never stands without its question; one heard live as well (the same text within ASKED_S) is drawn once.
// 3.6.0.17 P2: a `!` command refused from this panel shows once, as in the terminal: the panel's own answer row
// (`!<cmd>` over `denied: <reason>`) takes out the session's error line of the Controller's type for it
// (DENIED_TYPE, controller.py run_bang), told by that type, never by its words; a refusal in the terminal keeps its line.
import type { LiveLine } from "../shared/liveFeed";
import type { Out, Turn } from "./promptStore";

export type Row = { ts: number; n: number; turn?: Turn; line?: LiveLine; out?: Out };
const SHOWN: LiveLine["kind"][] = ["text", "tool", "ask", "state", "error", "output", "you"];
const ASKED_S = 120; // a turn heard live and its transcript line carry the session's own times: seconds apart at most
const DENIED_TYPE = "inline_shell_denied";

// n: its own key beside the heard turns' (PromptFeed's "t" + n)
const asTurn = (l: LiveLine, sid: string): Turn => ({ n: -l.n, sid, ts: l.ts, text: l.text, via: "", receipt: "", turn: 0 });
const same = (t: Turn, l: LiveLine) => Math.abs(t.ts - l.ts) <= ASKED_S && (t.text === l.text || (l.text.startsWith("...") && t.text.endsWith(l.text.slice(3))));
const deniedHere = (o: Out) => o.line.startsWith("!") && (o.lines[0] || "").startsWith("denied:");

/** The error lines of a refused `!` that this panel's own answer rows already show (one line for each row). */
function shownByOuts(lines: LiveLine[], outs: Out[]): Set<LiveLine> {
  const taken = new Set<LiveLine>();
  for (const o of outs.filter(deniedHere)) {
    const near = lines.filter((l) => !taken.has(l) && l.errType === DENIED_TYPE && Math.abs(l.ts - o.ts) <= ASKED_S);
    near.sort((a, b) => Math.abs(a.ts - o.ts) - Math.abs(b.ts - o.ts));
    if (near[0]) taken.add(near[0]);
  }
  return taken;
}

export function feedRows(turns: Turn[], lines: LiveLine[], outs: Out[], sid: string, key: string, max: number): Row[] {
  const mine = turns.filter((t) => t.sid === sid);
  const used = new Set<Turn>();
  const asked = lines.filter((l) => l.key === key && l.kind === "asked").filter((l) => {
    const t = mine.find((x) => !used.has(x) && same(x, l));
    return t ? (used.add(t), false) : true;
  });
  const ours = outs.filter((o) => o.sid === sid);
  const shown = lines.filter((l) => l.key === key && SHOWN.includes(l.kind));
  const told = shownByOuts(shown.filter((l) => l.kind === "error"), ours);
  const out: Row[] = [
    ...mine.map((t) => ({ ts: t.ts, n: t.n, turn: t })),
    ...asked.map((l) => ({ ts: l.ts, n: l.n, turn: asTurn(l, sid) })),
    ...shown.filter((l) => !told.has(l)).map((l) => ({ ts: l.ts, n: l.n, line: l })),
    ...ours.map((o) => ({ ts: o.ts, n: o.n, out: o })),
  ];
  out.sort((a, b) => a.ts - b.ts || a.n - b.n);
  return out.slice(-max);
}
