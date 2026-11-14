// Try it on a throwaway copy (3.6.0.0 R2; the approved mock): a test request, the cost band said first, Send / Stop,
// and the run as it goes -- each step's state, the agents that ran with their time and cost and what they handed on,
// each repeat's check (yes / no and why), the total, where it ran. The copy is thrown away after.
import { useEffect } from "react";
import { Button, TextBox } from "../../../lib/ui";
import { studio, useStore } from "../../../lib/store";
import type { TryRec, Workflow } from "../types";
import { costNow, useFlows } from "./flowStore";
import { markFlowSeen, running, setFlowTryText, startFlowTry, stopFlowTry, useFlowTry } from "./flowRun";

const STATE: Record<string, string> = { running: "running", stopping: "stopping", done: "done", stopped: "stopped by you", failed: "failed" };
const NONE: string[] = [];
const money = (v: number | null | undefined) => (typeof v === "number" ? `$${v.toFixed(4)}` : "cost unknown");

function Steps({ r }: { r: TryRec }) {
  return (
    <ol className="fl-try-steps" data-testid="flow-try-steps">
      {(r.steps || []).map((s) => (
        <li key={s.n} className="fl-try-step" data-state={s.state} data-testid="flow-try-step" data-n={s.n}>
          <div className="cw-row"><b>{s.n} · {s.name}</b><span className="cw-line mono" data-testid="flow-try-step-state">{s.state}</span>
            {s.state !== "waiting" && s.state !== "skipped" && <span className="cw-line">{money(s.cost_usd)}</span>}</div>
          {s.state === "skipped" && <div className="cw-line">{s.why}</div>}
          {s.agents.map((a) => (
            <div key={a.name} className="fl-try-agent" data-testid="flow-try-agent" data-name={a.name}>
              <span className="cw-line mono">{a.name} · {a.state}{a.seconds != null ? ` · ${a.seconds} s` : ""}{a.cost_usd != null ? ` · ${money(a.cost_usd)}` : ""}</span>
              {a.text && <div className="cw-reply-text">{a.text}</div>}
              {a.error && <div className="cw-line" data-tone="bad">{a.error}</div>}
            </div>
          ))}
          {(r.checks || []).filter((c) => c.n === s.n).map((c) => (
            <div key={c.round} className="cw-line" data-testid="flow-try-check">round {c.round}: the check said {c.yes ? "yes" : "no"}{c.line ? ` -- ${c.line}` : ""}</div>
          ))}
          {s.stop && <div className="cw-line" data-testid="flow-try-stop-why">{s.rounds} round{s.rounds === 1 ? "" : "s"}: {s.stop}</div>}
        </li>
      ))}
    </ol>
  );
}

function Result({ r }: { r: TryRec }) {
  const live = running(r);
  return (
    <div className="cw-reply" data-state={r.state} data-testid="flow-try-result" aria-live="polite">
      <div className="cw-reply-head mono"><span data-testid="flow-try-state">{STATE[r.state] || r.state}</span>
        <span className="cw-line">{live ? r.now || "starting..." : r.line || ""}</span></div>
      <Steps r={r} />
      {r.error && <div className="cw-line" data-tone="bad" data-testid="flow-try-error">{r.error}</div>}
      {r.denied?.length > 0 && <ul className="cw-asks">{r.denied.map((d, i) => <li key={i}>asked: {d} -- answered no (Try it does not wait for you)</li>)}</ul>}
      {!live && <div className="cw-line" data-testid="flow-try-total">{r.seconds ?? "?"} s · <b>{money(r.cost_usd)}</b>{r.where ? ` · ran in ${r.where}` : ""}</div>}
    </div>
  );
}

export function FlowTry({ w }: { w: Workflow }) {
  const text = useFlowTry((s) => s.text);
  const rec = useFlowTry((s) => s.rec);
  const busy = useFlowTry((s) => s.busy);
  const now = useFlows(costNow); // the band of the form as it stands (null while it is read)
  const cost = now?.cost;
  const missing = now?.missing || NONE;
  const here = useStore(studio, (s) => s.section === "agents");
  const live = running(rec);
  const mine = !!rec && rec.workflow === w.name;
  useEffect(() => { // the result drawn while the page is in view: seen (else it waits in Attention)
    if (!rec || live || rec.seen || !mine || !here) return undefined;
    const mark = () => document.visibilityState === "visible" && void markFlowSeen(rec.id);
    mark();
    document.addEventListener("visibilitychange", mark);
    return () => document.removeEventListener("visibilitychange", mark);
  }, [rec, live, mine, here]);
  const blocked = !w.steps.length ? "Add a step first." : missing.length ? `Make ${missing.join(", ")} first (or take it out of its step).` : "";
  return (
    <div className="cw-field" data-testid="flow-try">
      <span className="cw-label mono">Try it on a throwaway copy</span>
      <div className="cw-try">
        <TextBox value={text} onChange={(e) => setFlowTryText(e.target.value)} placeholder="A test request, e.g. Apply the discount before tax in basket.py"
                 data-testid="flow-try-text" aria-label="A test request" maxRows={6} />
        <div className="cw-row">
          {live
            ? <Button variant="danger" onClick={() => void stopFlowTry()} data-testid="flow-try-stop">Stop</Button>
            : <Button variant="primary" disabled={!text.trim() || busy || !!blocked} onClick={() => void startFlowTry()} data-testid="flow-try-send">Try it</Button>}
          <span className="cw-line" data-testid="flow-try-estimate">
            {blocked || `Runs every step once, as the form holds it now, on a copy of the project that is thrown away after; nothing in your project changes. It costs one run: ${cost?.line || "reading the prices..."}.`}
          </span>
        </div>
        {rec && mine && <Result r={rec} />}
      </div>
    </div>
  );
}
