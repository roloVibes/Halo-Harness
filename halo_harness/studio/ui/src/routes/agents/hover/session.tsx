// A session box's hover card (3.3.16.1): its whole title, where it works (project, branch, clean / dirty, ahead /
// behind, worktree), its kind when it is not the terminal's, its model, cost, agents live of all, what waits on you and
// since when it runs. A click selects its main agent: the agent inspector.
import { short } from "../../orchestra/format";
import { usePanels } from "../../fleet/pstore";
import { isLive, useFleet } from "../../fleet/store";
import type { SessionRow } from "../../fleet/types";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { ago, joined, plural, spent } from "./words";

/** "2 asks · the oldest: git push origin feature/basket", "" when nothing waits. */
function waits(s: SessionRow): string {
  const asks = Object.values(s.pending || {}).flatMap((v) => v || []);
  const waiting = (s.agents || []).filter((a) => a.state === "waiting").length;
  const n = Math.max(asks.length, waiting);
  if (!n) return "";
  return joined([plural(n, "ask"), asks[0] && `the oldest: ${short(asks[0], 48)}`]);
}

export function SessionHover({ hid, sid, title }: { hid: string; sid: string; title: string }) {
  const s = useFleet((st) => st.harnesses.find((h) => h.id === hid)?.sessions.find((x) => x.session_id === sid));
  const room = usePanels((st) => st.conflicts?.rooms.flatMap((r) => r.cards).find((x) => x.harness === hid && x.session_id === sid));
  if (!s) return null;
  const p = s.project || {};
  const folder = String(p.repo || p.root || s.cwd || "").replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "";
  const dirty = room?.dirty ?? p.dirty;
  const where = joined([folder, p.branch, p.branch && (dirty ? "dirty" : "clean"), !!room?.ahead && `ahead ${room.ahead}`, !!room?.behind && `behind ${room.behind}`,
                        !!room?.worktree && `worktree ${String(room.worktree).replace(/[\\/]+$/, "").split(/[\\/]/).pop()}`]);
  const agents = s.agents || [];
  const kind = s.kind && s.kind !== "tui" ? (s.kind === "headless" ? "no terminal (started from Studio)" : s.kind) : "";
  const cost = spent(s.cost_usd);
  const rows: HoverRow[] = [
    ["Where", where],
    ["Kind", kind],
    ["Model", joined([s.model, s.effort])],
    ["Cost", cost && (s.cost_complete === false ? `${cost}+ (a model gave no price)` : cost)],
    ["Agents", agents.length ? `${agents.filter(isLive).length} live of ${agents.length}` : ""],
    ["Waits on you", waits(s)],
    ["Started", ago(s.started)],
  ];
  return <HoverBody title={title} is={s.cwd ? `A session in ${s.cwd}` : "A session of this machine"} rows={rows} foot="Click: its main agent in the inspector" />;
}
