// The inline answer for a session that waits on you, shown in the Fleet
// tree (routes/fleet/FleetTree.tsx, Fleet's Tree panel since 3.3.2.0 R2;
// 3.0.5.0 replaced the rail's plain list of live sessions with that tree). It posts `answer` to the session's command
// route (`sessions/<sid>/command` here, `fleet/<harness>/<sid>/command` for a
// member): an approval card takes accept / an instruction / stop, a
// permission card allow / deny, a plan approve / send back. A question stays
// in the terminal (it needs the typed answer).
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { toast, type SessionInfo } from "../lib/store";
import { Button } from "../lib/ui";

async function send(path: string, body: Record<string, unknown>, done: string): Promise<boolean> {
  try {
    await api.post(path, { cmd: "answer", ...body });
    toast(done, "done");
    return true;
  } catch (e) {
    toast(e instanceof ApiError ? e.message : String(e), "error", 5000);
    return false;
  }
}

export function Answer({ s, after, path }: { s: SessionInfo; after: () => void; path?: string }) {
  const [text, setText] = useState("");
  const p = s.pending || {};
  const route = path || `sessions/${encodeURIComponent(s.session_id)}/command`;
  const go = async (body: Record<string, unknown>, done: string) => {
    if (await send(route, body, done)) {
      setText("");
      after();
    }
  };
  return (
    <div className="rail-answer" data-motion="waiting" data-testid="rail-answer">
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
