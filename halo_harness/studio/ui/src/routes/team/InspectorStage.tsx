// The Team Inspector's stage face (3.0.8.0 R2): the stage's board row (state,
// members, lead, gate, trigger, cost, summary, error, waiting), Run (`POST
// team/run {stage}`: a 422 lists the problems right here; a preflight 422
// adds "Run anyway" = force) and, while the stage waits at its gate, the gate
// card: its text, the summary, the acceptance's ok and note, Accept, Redo
// with an instruction, Stop (`POST team/answer`).
import { useState } from "react";
import { Button } from "../../lib/ui";
import { answerGate, runStage } from "./actions";
import { elapsed, openGate, rowOf, specOf, usd, useTeam } from "./store";
import type { Gate } from "./types";

const KIND: Record<string, string> = { agent: "an agent turn", orchestra: "an Orchestra run", flow: "a flow" };

function GateCard({ g }: { g: Gate }) {
  const [text, setText] = useState("");
  const busy = useTeam((s) => s.busy === "answer");
  const go = async (action: "accept" | "redo" | "stop") => {
    if (await answerGate(g.stage, action, action === "redo" ? text.trim() : "")) setText("");
  };
  const acc = g.acceptance;
  return (
    <div className="tm-gatecard" data-motion="waiting" data-testid="team-gate-card" data-stage={g.stage}>
      <div className="tm-gatecard-head">
        <span className="glance-kicker mono tm-warn">WAITING ON YOU</span>
        <span className="mono muted">{g.stage} · round {g.round} · {g.gate} gate</span>
      </div>
      <p className="tm-gate-text">{g.text}</p>
      {g.summary && <pre className="tm-gate-summary" data-testid="team-gate-summary">{g.summary}</pre>}
      {acc && (
        <p className="tm-acc mono" data-ok={acc.ok || undefined} data-testid="team-gate-acceptance">
          acceptance {acc.ok ? "ok" : "failed"}{acc.note ? `: ${acc.note}` : ""}
        </p>
      )}
      <div className="tm-gate-actions">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => void go("accept")} title="Mark the stage done; the stages waiting on it start" data-testid="team-accept">Accept</Button>
        <input className="input tm-redo-text" placeholder="what to change, then Redo" value={text} onChange={(e) => setText(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && text.trim() && void go("redo")} aria-label="Redo instruction" data-testid="team-redo-text" />
        <Button size="sm" disabled={busy || !text.trim()} onClick={() => void go("redo")} title="Run the stage again with the instruction" data-testid="team-redo">Redo</Button>
        <Button variant="danger" size="sm" disabled={busy} onClick={() => void go("stop")} title="End the run here: every stage not done is skipped" data-testid="team-gate-stop">Stop</Button>
      </div>
    </div>
  );
}

function Problems() {
  const p = useTeam((s) => s.runProblems);
  const busy = useTeam((s) => s.busy === "run");
  if (!p) return null;
  return (
    <div className="tm-problems" data-testid="team-run-problems" data-preflight={p.preflight || undefined}>
      <b>{p.preflight ? "The lineup preflight stops this stage:" : "The team file has problems:"}</b>
      <ul>{p.problems.map((x) => <li key={x}>{x}</li>)}</ul>
      {p.preflight && (
        <Button size="sm" variant="danger" disabled={busy} onClick={() => void runStage(p.stage || null, true)} title="Run with the findings as they are" data-testid="team-run-anyway">Run anyway</Button>
      )}
    </div>
  );
}

export function StageFace({ id }: { id: string }) {
  const row = useTeam((s) => rowOf(s, id));
  const spec = useTeam((s) => specOf(s, id));
  const gate = useTeam((s) => openGate(s, id));
  const busy = useTeam((s) => s.busy === "run");
  const started = useTeam((s) => s.board?.created || 0);
  if (!spec) return <p className="muted">Stage {id} is not in the team file any more.</p>;
  const state = row?.state || "pending";
  const members = row?.members?.length ? row.members : spec.members;
  const runnable = !["running", "gated"].includes(state);
  const kv: [string, string][] = [
    ["state", state + (row?.round && row.round > 1 ? ` (round ${row.round})` : "")],
    ["kind", KIND[spec.kind] || spec.kind],
    ["members", members.join(", ") || (spec.kind === "agent" ? "the first member" : "none (it runs here)")],
    ["lead", row?.lead || spec.lead || "-"],
    ["gate", spec.gate],
    ["trigger", spec.trigger + (spec.trigger.startsWith("block_change") ? ` (settles ${spec.settle_s}s)` : "")],
    ["reads", spec.reads.join(", ") || "-"],
    ["writes", spec.writes.join(", ") || "-"],
    ["cost", usd(row?.cost_usd)],
  ];
  if (row?.started) kv.push(["took", row.ended ? elapsed(row.ended - row.started) : `running ${elapsed(Date.now() / 1000 - row.started)}`]);
  if (row?.started && started) kv.push(["started at", "+" + elapsed(row.started - started)]);
  return (
    <div className="tm-face" data-testid="team-stage-face" data-stage={id} data-state={state}>
      <div className="tm-face-head">
        <b className="tm-face-title">{id}</b>
        <span className="og-chip mono tm-run-state" data-state={state}>{state}</span>
        <span className="spacer" />
        <Button size="sm" variant="primary" disabled={busy || !runnable} onClick={() => void runStage(id)}
                title={runnable ? "Start this stage now (POST team/run)" : state === "gated" ? "It waits at its gate: answer below" : "It runs now"} data-testid="team-run-stage">Run</Button>
      </div>
      <Problems />
      {gate && <GateCard g={gate} />}
      {row?.waiting && <p className="tm-waiting mono" data-testid="team-stage-waiting">{row.waiting}</p>}
      {row?.error && <p className="tm-error" data-testid="team-stage-error">{row.error}</p>}
      <dl className="tm-kv mono">
        {kv.map(([k, v]) => (
          <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      {row?.summary && (
        <>
          <div className="glance-kicker mono">SUMMARY</div>
          <pre className="tm-summary" data-testid="team-stage-summary">{row.summary}</pre>
        </>
      )}
      {row?.gate_answer && <p className="muted tm-answered mono">answered {row.gate_answer.action}{row.gate_answer.text ? `: ${row.gate_answer.text}` : ""} (round {row.gate_answer.round})</p>}
      {spec.prompt && <p className="muted tm-prompt">prompt: {spec.prompt}</p>}
    </div>
  );
}
