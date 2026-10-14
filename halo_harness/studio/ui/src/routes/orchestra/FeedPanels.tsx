// The live feed and sessions panels: Glance = one live indicator and one or
// two big numbers; Expand = the recent frames / the session list.
import { Empty } from "../../lib/ui";
import { studio, useStore, type FeedStatus } from "../../lib/store";
import { useRecent, useStateMotion, type MotionState } from "../../lib/motion";
import { recent } from "../../shell/feed";

const STATUS_TEXT: Record<FeedStatus, string> = {
  off: "off",
  connecting: "connecting",
  open: "connected",
  retrying: "reconnecting",
  down: "unreachable",
};

export function useFeedMotion(): MotionState {
  const status = useStore(studio, (s) => s.feed.status);
  const lastTs = useStore(studio, (s) => s.feed.lastTs);
  const busy = useRecent(lastTs, 2500);
  if (status === "down") return "error";
  if (status === "retrying" || status === "connecting") return "waiting";
  return busy ? "working" : "idle";
}

export function useSessionsMotion(): MotionState {
  const n = useStore(studio, (s) => s.feed.sessions.length);
  return n ? "idle" : "none";
}

export function FeedDot() {
  const status = useStore(studio, (s) => s.feed.status);
  const events = useStore(studio, (s) => s.feed.events);
  const motion = useStateMotion(status === "open" ? "live" : status === "down" ? "error" : status === "off" ? "none" : "waiting", events);
  return <span className="feed-dot" data-status={status} {...motion} aria-label={`live feed ${STATUS_TEXT[status]}`} />;
}

export function FeedGlance() {
  const feed = useStore(studio, (s) => s.feed);
  return (
    <div className="glance">
      <div className="glance-row">
        <FeedDot />
        <span className="glance-kicker mono">FEED {STATUS_TEXT[feed.status].toUpperCase()}</span>
      </div>
      <div className="glance-numbers">
        <div className="metric">
          <span className="metric-value mono">{feed.events}</span>
          <span className="metric-label">events</span>
        </div>
        <div className="metric">
          <span className="metric-value mono">{feed.sessions.length}</span>
          <span className="metric-label">sessions</span>
        </div>
      </div>
      <div className="glance-hint mono">{feed.lastKind ? `last: ${feed.lastKind}` : "waiting for the first event"}</div>
    </div>
  );
}

function when(ts: number): string {
  const d = new Date(ts > 1e12 ? ts : ts * 1000);
  return d.toTimeString().slice(0, 8);
}

export function FeedDetail() {
  const frames = useStore(recent, (r) => r.frames);
  if (!frames.length)
    return <Empty title="No events yet" body="Start a Halo session in a terminal (halo); its events stream here as it works." />;
  return (
    <ol className="feed-list mono" aria-label="recent events">
      {frames
        .slice()
        .reverse()
        .map((f, i) => (
          <li key={frames.length - i} className="feed-row" data-kind={f.event}>
            <span className="feed-time">{when(f.ts)}</span>
            <span className="feed-kind">{f.event}</span>
            <span className="feed-sid">{(f.session_id || "").slice(0, 8)}</span>
            {f.agent_id && <span className="feed-agent">{f.agent_id}</span>}
          </li>
        ))}
    </ol>
  );
}

export function SessionsGlance() {
  const sessions = useStore(studio, (s) => s.feed.sessions);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <div className="metric">
          <span className="metric-value mono">{sessions.length}</span>
          <span className="metric-label">live session{sessions.length === 1 ? "" : "s"}</span>
        </div>
      </div>
      <div className="glance-hint">{sessions.length ? sessions.map((s) => s.title || s.session_id.slice(0, 8)).slice(0, 3).join(" · ") : "None attached. Run halo in a terminal."}</div>
    </div>
  );
}

export function SessionsDetail() {
  const sessions = useStore(studio, (s) => s.feed.sessions);
  if (!sessions.length) return <Empty title="No live sessions" body="Each running halo session appears here within two seconds of starting." />;
  return (
    <ul className="session-list">
      {sessions.map((s) => (
        <li key={s.session_id} className="session-row">
          <span className="session-title">{s.title || "untitled"}</span>
          <span className="session-meta mono">
            {s.session_id.slice(0, 8)} · {s.kind || "tui"} · {s.mode || "default"}
          </span>
          {s.cwd && <span className="session-cwd mono">{s.cwd}</span>}
        </li>
      ))}
    </ul>
  );
}
