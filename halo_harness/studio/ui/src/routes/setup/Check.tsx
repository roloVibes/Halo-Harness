// setup-check (3.3.0.0 R3): the checks Halo offers after setup
// (checks/catalog.py: doctor, catalog, hello, the steward, the gym),
// each row with what it does, what it costs, how long it takes and what it
// writes; doctor, catalog and hello are ticked. "Run the ticked checks" runs
// them in order as one background job (POST setup/check) and each row shows
// its state and its lines as they arrive. The gym row lists the models it
// would run on (only local models run). 3.4.0.0 B: the guided first run is the first-run pack's Setup check now,
// a row under "From packs" while that pack is on. 3.3.11.0 R3: an enabled pack's Setup checks follow under "From packs",
// each with its own what / cost / time / writes line and unticked until you tick it; they run in the same job.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { useLoadState, Waiting } from "./BlockFoot";
import { lastCheckWord, runChecks, startCheck, stopChecks, tick, tickModel, ticked, useCheck } from "./checkStore";
import { packBlocks, type Found } from "./packSetup";
import { NONE, setup, useSetup, type CheckRow } from "./store";

const GLYPH: Record<string, string> = { running: ">>", done: "ok", failed: "!!", pending: "..", stopped: "--", ready: ".." };

function GymModels() {
  const models = useSetup((s) => s.data?.gym_models || NONE);
  const ticks = useCheck((s) => s.models);
  if (!models.length) return <p className="su-note muted" data-testid="setup-check-gym-none">No model to run yet: save a default model first.</p>;
  return (
    <ul className="su-check-models" data-testid="setup-check-gym-models">
      {models.map((m) => (
        <li key={m.ref}>
          <label className="su-check-model" data-testid="setup-check-gym-model" data-ref={m.ref}>
            <input type="checkbox" checked={ticks[m.ref] !== false} onChange={(e) => tickModel(m.ref, e.target.checked)} />
            <span className="mono">{m.ref}</span> <span className="muted">{m.cost}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}

export function Row({ c, pack }: { c: CheckRow; pack?: string }) {
  const on = useCheck((s) => ticked(s, setup.get().data, c.key));
  const frame = useCheck((s) => s.frames[c.key]);
  const running = useCheck((s) => s.running || s.busy);
  const state = frame?.state || "";
  return (
    <div className="su-check" data-testid="setup-check-row" data-key={c.key} data-state={state || undefined}>
      <label className="su-check-head">
        <input type="checkbox" checked={on} disabled={running} onChange={(e) => tick(c.key, e.target.checked)}
               data-testid="setup-check-tick" data-key={c.key} />
        <span className="su-glyph mono" data-testid="setup-check-glyph" data-key={c.key}>{GLYPH[state] || ""}</span>
        <b>{c.title}</b>
        <span className="muted mono">({pack || c.key})</span>
      </label>
      <span className="su-check-detail muted">
        {c.what}. Cost: {c.cost}. Time: {c.time}. Writes: {c.writes}.
      </span>
      {c.key === "gym" && on && <GymModels />}
      {frame && frame.lines.length > 0 && (
        <pre className="su-check-log mono" data-state={state} data-testid="setup-check-log" data-key={c.key}>
          {frame.lines.join("\n")}
        </pre>
      )}
    </div>
  );
}

function Summary() {
  const summary = useCheck((s) => s.summary);
  const running = useCheck((s) => s.running);
  const last = useSetup((s) => s.data?.last_check);
  if (running) return <span className="su-word mono" data-testid="setup-check-summary" data-word="running">running...</span>;
  if (summary) {
    const failed = summary.results.filter((r) => !r.ok).map((r) => r.key);
    const text = failed.length ? `${failed.length} failed: ${failed.join(", ")}` : summary.stopped ? "stopped" : `all ${summary.results.length} passed`;
    return <span className="su-word mono" data-testid="setup-check-summary" data-word={failed.length ? "problem" : "saved"}>{text}</span>;
  }
  return <span className="su-word mono" data-testid="setup-check-summary">last check: {lastCheckWord(last)}</span>;
}

function checkRow(f: Found): CheckRow {
  const b = f.block;
  return { key: b.key, title: b.title, what: b.what || "", cost: b.cost || "", time: b.time || "", writes: b.writes || "", default_on: false };
}

/** 3.3.11.0 R3: the enabled packs' Setup checks, under "From packs", unticked until ticked. */
function PackRows() {
  const joined = useSetup((s) => JSON.stringify(packBlocks(s.data).filter((f) => f.block.kind === "check").map((f) => [f.pack.name, checkRow(f)])));
  const rows = JSON.parse(joined) as [string, CheckRow][];
  if (!rows.length) return null;
  return (
    <div className="su-checks" data-testid="setup-check-packs">
      <div className="su-check-from mono muted" data-testid="setup-check-from-packs">From packs</div>
      {rows.map(([pack, c]) => (
        <Row key={c.key} c={c} pack={pack} />
      ))}
    </div>
  );
}

export function CheckDetail() {
  const { ready, error } = useLoadState();
  const rows = useSetup((s) => s.data?.checks || NONE);
  const running = useCheck((s) => s.running);
  const busy = useCheck((s) => s.busy);
  const any = useCheck((s) => rows.some((c) => ticked(s, setup.get().data, c.key)) || Object.entries(s.ticks).some(([k, on]) => on && k.startsWith("pack:")));
  const problem = useCheck((s) => s.error);
  useEffect(() => void startCheck(), []);
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-check">
      <p className="su-lead muted">Tick the checks to run; each says what it does, costs, takes and writes. The same ones as halo check in a terminal.</p>
      <div className="su-checks">
        {rows.map((c) => (
          <Row key={c.key} c={c} />
        ))}
      </div>
      <PackRows />
      <div className="su-foot-row">
        <Button variant="primary" size="sm" onClick={() => void runChecks()} disabled={busy || running || !any} data-testid="setup-check-run">
          {busy ? "Starting..." : "Run the ticked checks"}
        </Button>
        {running && (
          <Button variant="ghost" size="sm" onClick={() => void stopChecks()} data-testid="setup-check-stop">
            Stop after this check
          </Button>
        )}
        <Summary />
      </div>
      {problem && <p className="su-error" data-testid="setup-check-error">{problem}</p>}
    </div>
  );
}

export function CheckGlance() {
  const last = useSetup((s) => s.data?.last_check);
  const running = useCheck((s) => s.running);
  return (
    <div className="glance">
      <div className="glance-kicker mono">CHECK</div>
      <div className="glance-text">{running ? "running..." : lastCheckWord(last)}</div>
      <div className="glance-hint">doctor, catalog, hello, the gym, the guided first run</div>
    </div>
  );
}
