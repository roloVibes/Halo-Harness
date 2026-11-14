// Try it (3.6.0.0 R1): a test request, what one task costs on the picked model said before the run, Send / Stop, and
// the result in the tab -- its reply, the tools it used, what it asked (a Try it run does not wait for you: each ask is
// answered no and listed), its time and cost, and where it ran. The run is the agent as the form holds it now.
import { useEffect } from "react";
import { Button, TextBox } from "../../lib/ui";
import { useStore, studio } from "../../lib/store";
import { markSeen, setTryText, startTry, stopTry, useTry } from "./tryStore";
import type { Agent, TryRec } from "./types";

const STATE: Record<TryRec["state"], string> = { running: "running", stopping: "stopping", done: "done", stopped: "stopped by you", failed: "failed" };

function money(v: number | null | undefined): string {
  return typeof v === "number" ? `$${v.toFixed(4)}` : "cost unknown";
}

function Result({ r }: { r: TryRec }) {
  const used = Object.entries(r.used || {}).map(([t, n]) => `${t}${n > 1 ? ` x${n}` : ""}`).join(", ") || "no tools";
  const live = r.state === "running" || r.state === "stopping";
  return (
    <div className="cw-reply" data-state={r.state} data-testid="crew-try-result" aria-live="polite">
      <div className="cw-reply-head mono">
        <span data-testid="crew-try-state">{STATE[r.state]}</span>
        <span className="cw-line" title={r.model_line}>{r.model_line}</span>
      </div>
      {live && <div className="cw-line" data-testid="crew-try-now">{r.now || "working..."}</div>}
      {r.reply && <div className="cw-reply-text" data-testid="crew-try-reply">{r.reply}</div>}
      {r.error && <div className="cw-line" data-tone="bad" data-testid="crew-try-error">{r.error}</div>}
      {r.denied?.length > 0 && (
        <ul className="cw-asks" data-testid="crew-try-asks">
          {r.denied.map((d, i) => <li key={i}>asked: {d} -- answered no (Try it does not wait for you)</li>)}
        </ul>
      )}
      {!live && (
        <div className="cw-line" data-testid="crew-try-used">
          Used: {used} · {r.seconds ?? "?"} s · <b>{money(r.cost_usd)}</b>{r.where ? ` · ran in ${r.where}` : ""}
        </div>
      )}
    </div>
  );
}

export function TryIt({ a }: { a: Agent }) {
  const text = useTry((s) => s.text);
  const rec = useTry((s) => s.rec);
  const busy = useTry((s) => s.busy);
  const est = useTry((s) => s.estimate);
  const here = useStore(studio, (s) => s.section === "agents");
  const live = !!rec && (rec.state === "running" || rec.state === "stopping");
  const mine = !!rec && rec.agent === a.name;
  useEffect(() => { // the result drawn while the page is in view: seen (else it waits in Attention)
    if (!rec || live || rec.seen || !mine || !here) return undefined;
    const mark = () => document.visibilityState === "visible" && void markSeen(rec.id);
    mark();
    document.addEventListener("visibilitychange", mark);
    return () => document.removeEventListener("visibilitychange", mark);
  }, [rec, live, mine, here]);
  return (
    <div className="cw-field" data-testid="crew-try">
      <span className="cw-label mono">Try it</span>
      <div className="cw-try">
        <TextBox value={text} onChange={(e) => setTryText(e.target.value)} placeholder="A test request, e.g. Review the diff of the last commit"
                 data-testid="crew-try-text" aria-label="A test request" maxRows={6} />
        <div className="cw-row">
          {live
            ? <Button variant="danger" onClick={() => void stopTry()} data-testid="crew-try-stop">Stop</Button>
            : <Button variant="primary" disabled={!text.trim() || busy} onClick={() => void startTry()} data-testid="crew-try-send">Send a test request</Button>}
          <span className="cw-line" data-testid="crew-try-estimate">
            Runs this agent once, as the form holds it now (saved or not), on a throwaway copy of the project. {est ? `Cost: ${est.line}.` : "Reading the price..."}
          </span>
        </div>
        {rec && mine && <Result r={rec} />}
      </div>
    </div>
  );
}
