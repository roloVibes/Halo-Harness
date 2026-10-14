// The rail's live sessions: each with its status badge (GET sessions asks
// each session's control socket: waiting | busy | idle | unknown) and, for a
// session that waits on you, an inline answer that posts to
// `sessions/<sid>/command`: an org approval card takes accept / an
// instruction / stop, a permission card allow / deny, a plan approve / send
// back. A question stays in the terminal (it needs the typed answer).
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { studio, toast, useStore, type SessionInfo } from "../lib/store";
import { Button, Empty } from "../lib/ui";

const POLL_MS = 4000; // while a session is live
const IDLE_MS = 15000; // while none is

async function send(sid: string, body: Record<string, unknown>, done: string): Promise<boolean> {
  try {
    await api.post(`sessions/${encodeURIComponent(sid)}/command`, { cmd: "answer", ...body });
    toast(done, "done");
    return true;
  } catch (e) {
    toast(e instanceof ApiError ? e.message : String(e), "error", 5000);
    return false;
  }
}

function Answer({ s, after }: { s: SessionInfo; after: () => void }) {
  const [text, setText] = useState("");
  const p = s.pending || {};
  const go = async (body: Record<string, unknown>, done: string) => {
    if (await send(s.session_id, body, done)) {
      setText("");
      after();
    }
  };
  return (
    <div className="rail-answer" data-motion="waiting">
      {(p.approval || []).map((rid) => (
        <div key={rid} className="rail-answer-card">
          <div className="mono muted">approval · {rid}</div>
          <input className="input" value={text} placeholder="instruction (what to change)" onChange={(e) => setText(e.target.value)} aria-label="Instruction" />
          <div className="og-actions">
            <Button size="sm" variant="primary" onClick={() => void go({ kind: "approval", request_id: rid, action: "accept" }, "Approval accepted")}>Accept</Button>
            <Button size="sm" disabled={!text.trim()} onClick={() => void go({ kind: "approval", request_id: rid, action: "edit", instruction: text }, "Instruction sent")}>Send</Button>
            <Button size="sm" variant="danger" onClick={() => void go({ kind: "approval", request_id: rid, action: "stop" }, "Stopped")}>Stop</Button>
          </div>
        </div>
      ))}
      {(p.permission || []).map((rid) => (
        <div key={rid} className="rail-answer-card">
          <div className="mono muted">permission · {rid}</div>
          <div className="og-actions">
            <Button size="sm" variant="primary" onClick={() => void go({ kind: "permission", request_id: rid, action: "allow", scope: "once" }, "Allowed once")}>Allow once</Button>
            <Button size="sm" onClick={() => void go({ kind: "permission", request_id: rid, action: "deny" }, "Denied")}>Deny</Button>
          </div>
        </div>
      ))}
      {(p.plan || []).length > 0 && (
        <div className="rail-answer-card">
          <div className="mono muted">plan</div>
          <input className="input" value={text} placeholder="feedback (to send it back)" onChange={(e) => setText(e.target.value)} aria-label="Feedback" />
          <div className="og-actions">
            <Button size="sm" variant="primary" onClick={() => void go({ kind: "plan", approved: true }, "Plan approved")}>Approve</Button>
            <Button size="sm" disabled={!text.trim()} onClick={() => void go({ kind: "plan", approved: false, feedback: text }, "Plan sent back")}>Send back</Button>
          </div>
        </div>
      )}
      {(p.question || []).length > 0 && <div className="mono muted">a question: answer it in the terminal</div>}
    </div>
  );
}

export function Sessions() {
  const feedRows = useStore(studio, (s) => s.feed.sessions);
  const [rows, setRows] = useState<SessionInfo[] | null>(null);
  const [open, setOpen] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .get<SessionInfo[]>("sessions")
        .then((r) => alive && setRows(Array.isArray(r) ? r : []))
        .catch(() => alive && setRows(null));
    void load();
    const id = window.setInterval(load, feedRows.length || rows?.length ? POLL_MS : IDLE_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [tick, feedRows.length, !!rows?.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const byId = new Map((rows || []).map((r) => [r.session_id, r]));
  const list: SessionInfo[] = rows ? [...rows, ...feedRows.filter((f) => !byId.has(f.session_id))] : feedRows;
  return (
    <section className="rail-group" aria-label="Live sessions">
      <div className="rail-label mono">LIVE SESSIONS · {list.length}</div>
      {list.length ? (
        list.map((s) => {
          const st = s.status || "unknown";
          return (
            <div key={s.session_id} className="rail-session-wrap" data-testid="rail-session">
              <div className="rail-session" data-status={st}>
                <span className="rail-session-dot" data-status={st} data-motion={st === "waiting" ? "waiting" : "none"} aria-hidden="true" />
                <span className="rail-item-text" title={`${s.cwd || ""} ${s.model || ""}`}>{s.title || s.session_id.slice(0, 8)}</span>
                {!!s.agents && (
                  <span className="badge mono" title="sub-agents working right now" data-testid="session-agents">
                    {s.agents} {s.agents === 1 ? "agent" : "agents"}
                  </span>
                )}
                <span className="badge" data-status={st} data-testid="session-status">{st}</span>
                {st === "waiting" && (
                  <button className="og-link mono" onClick={() => setOpen(open === s.session_id ? "" : s.session_id)} aria-expanded={open === s.session_id}>
                    answer
                  </button>
                )}
              </div>
              {st === "waiting" && open === s.session_id && <Answer s={s} after={() => setTick((n) => n + 1)} />}
            </div>
          );
        })
      ) : (
        <Empty title="None yet" body="Run halo in a terminal: it shows up here." />
      )}
    </section>
  );
}
