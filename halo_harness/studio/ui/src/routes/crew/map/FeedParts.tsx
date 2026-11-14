// The drawer's other pages (3.6.0.0 R4b): what "What they think and say" shows besides a live run's rows --
// - `under:<id>`: the helpers a helper started (R4's gap 2, depth): one row each, "started by <who>", a click filters
//   the drawer to it; no second level is drawn on the map;
// - a replay's rows (gap 10): the run's spawns, hand-offs, asks, failures and finishes up to the scrubber's moment, from
//   Live's replay store (agents/live/replay.ts, its timeline's marks), filtered by the clicked box like a live run;
// - `plan`: the session's todo plan (todoStore.ts), one row per item with its state.
import { Empty } from "../../../lib/ui";
import { mmss } from "../live/timeline";
import { under, type Helper } from "./overlay";
import { setFeedFor } from "./litStore";
import { STATE_WORDS } from "./LitBits";
import type { Todo } from "./todoStore";
import type { Lit } from "./useLit";

export function UnderList({ L, aid }: { L: Lit; aid: string }) {
  const all = L.ov?.helpers || [];
  const top = all.find((h) => h.aid === aid);
  const list = under(all, aid);
  const name = (id: string) => all.find((h) => h.aid === id)?.name || (id === "main" ? "main" : id);
  return (
    <div className="mpf-under" data-testid="map-feed-under" data-of={aid}>
      <span className="cw-line">{top ? `${top.name} started ${list.length} helper${list.length === 1 ? "" : "s"}` : "Helpers"}: who started whom.</span>
      {list.map((h: Helper) => (
        <button key={h.aid} type="button" className="mpf-row-btn" data-testid="map-feed-under-row" data-aid={h.aid} onClick={() => setFeedFor(`agent:${h.aid}`)}
                title={`Show only what ${h.name} thinks and says`}>
          <b>{h.name}</b> <span className="mp-muted">started by {name(h.parent)} · {STATE_WORDS[h.state]}</span>
          {h.task && <span className="mpf-row-task">{h.task.length > 120 ? h.task.slice(0, 117) + "..." : h.task}</span>}
        </button>
      ))}
    </div>
  );
}

const MARK_WORDS: Record<string, string> = { spawn: "started", handoff: "handed back", ask: "asked", fail: "failed", finish: "finished" };

export function ReplayRows({ L, ids }: { L: Lit; ids: Set<string> | null }) {
  const r = L.replay;
  if (!r) return null;
  const name = new Map(r.tl.base.map((n) => [n.id, n.name]));
  const rows = r.tl.marks.filter((m) => m.t <= r.t + 1e-6 && (!ids || ids.has(m.agent_id) || (!!m.to && ids.has(m.to))));
  if (!rows.length) return <Empty title="Nothing yet at this moment" body="Move the scrubber on: each start, hand-off, ask and finish of the run shows here as it happened." testid="map-feed-replay-empty" />;
  return (
    <div className="mpf-rows" data-testid="map-feed-replay" data-t={Math.round(r.t)}>
      {rows.map((m, i) => (
        <div key={i} className="mpf-mark" data-testid="map-feed-replay-row" data-kind={m.kind}>
          <span className="mono mp-muted">{mmss(m.t - r.tl.t0)}</span>{" "}
          <b>{m.name || name.get(m.agent_id) || m.agent_id}</b> {MARK_WORDS[m.kind] || m.kind}
          {m.to && <> {m.kind === "spawn" ? "by" : "to"} {name.get(m.to) || m.to}</>}
          {m.text && <span className="mpf-row-task">{m.text.length > 200 ? m.text.slice(0, 197) + "..." : m.text}</span>}
        </div>
      ))}
    </div>
  );
}

const TODO_WORDS: Record<string, string> = { completed: "done", in_progress: "doing now", pending: "not yet" };

export function PlanList({ list }: { list: Todo[] | undefined }) {
  if (!list || !list.length) return <Empty title="No plan" body="When main keeps a todo plan, its items land here as it ticks them off." testid="map-feed-plan-none" />;
  return (
    <ol className="mpf-plan" data-testid="map-feed-plan">
      {list.map((t, i) => (
        <li key={i} className="mpf-plan-row" data-testid="map-feed-plan-row" data-status={t.status}>
          <span className="mono mp-muted">{TODO_WORDS[t.status] || t.status}</span> {t.status === "in_progress" && t.activeForm ? t.activeForm : t.content}
        </li>
      ))}
    </ol>
  );
}
