// The pages of a goal run's inspector on Live (3.4.0.0 D "the runs fold"; one block per page, R1b's rule): the plan (its
// jobs, each lane's owns line, what it runs after and takes), the claims (the claim ledger, with Release and Steal),
// the diff (each unit the lane holds: the base lines, then the lane's text), the test result (the gate's lines, the
// re-base's test, the report's tail) and the log (the run's timed lines). A lane's page shows that lane's part; the
// lead's shows the whole run. Runs' Workflow, Run grid, Live file, Lanes, Claims and Log panels drew these before.
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { elapsed, short } from "../../orchestra/format";
import { NONE, useOrch } from "../../orchestra/store";
import { loadFile, releaseClaim, stealClaim } from "../../orchestra/sync";
import type { Lane, RunPayload } from "../../orchestra/types";
import { ledgerOf, OwnsLine, ownsOf } from "./Owns";

export type RunPage = "plan" | "claims" | "diff" | "test" | "log";
export const PAGES: [RunPage, string][] = [["plan", "Plan"], ["claims", "Claims"], ["diff", "Diff"], ["test", "Test result"], ["log", "Log"]];

export function PlanPage({ data, lane }: { data: RunPayload; lane: Lane | null }) {
  const lanes = lane ? [lane] : data.lanes;
  const jobs = data.split?.jobs || [];
  if (!lanes.length && !jobs.length) return <p className="muted">No plan yet: the lead has not split the goal{data.run.state === "planned" ? " (it waits for your review)" : ""}.</p>;
  return (
    <ul className="rp-list" data-testid="run-page-plan-rows">
      {(lanes.length ? lanes : []).map((l) => (
        <li key={l.lane} className="rp-row" data-lane={l.lane}>
          <b className="mono">lane {l.lane}</b> {l.title || l.job}
          <OwnsLine keys={ownsOf(l, data.claims || NONE)} testid="plan-owns" />
          <span className="mono muted">{[l.after?.length ? `after ${l.after.join(", ")}` : "starts at once", (l.handoff?.needs || []).map((n) => `takes ${n.take} from ${n.from}`).join(", "),
            l.base ? `base ${l.base.slice(0, 7)}` : ""].filter(Boolean).join(" · ")}</span>
        </li>
      ))}
      {!lanes.length && jobs.map((j) => <li key={j.id} className="rp-row"><b className="mono">worker {j.worker}</b> {j.title} <OwnsLine keys={j.claims} testid="plan-owns" /></li>)}
    </ul>
  );
}

export function ClaimsPage({ data, lane }: { data: RunPayload; lane: Lane | null }) {
  const rows = lane ? ledgerOf(data.claims || NONE, ownsOf(lane, data.claims || NONE), lane) : data.claims || NONE;
  if (!rows.length) return <p className="muted mono" data-testid="lane-claims" data-count={0}>No claim held: a worker claims its units when it joins, and a finished run holds none.</p>;
  return (
    <ul className="ag-claims mono" data-testid="lane-claims" data-count={rows.length}>
      {rows.map((c) => (
        <li key={c.key} data-testid="lane-claim" data-state={c.state} data-holder={c.holder}>
          <span title={c.key}>{c.key}</span>
          <span className="muted">{c.holder}</span>
          <span>{c.state}</span>
          {data.live && <span className="rp-acts">
            <Button size="sm" variant="ghost" onClick={() => void releaseClaim(c.key)} title="Let the claim go: the unit is free for its lane again" data-testid="claim-release">Release</Button>
            <Button size="sm" variant="ghost" onClick={() => void stealClaim(c.key)} title="The run's lead takes the unit" data-testid="claim-steal">Steal</Button>
          </span>}
        </li>
      ))}
    </ul>
  );
}

export function DiffPage({ data, lane }: { data: RunPayload; lane: Lane | null }) {
  const files = useOrch((s) => s.files);
  const keys = lane ? lane.claims : data.lanes.flatMap((l) => l.claims);
  const paths = [...new Set(keys.map((k) => k.split("#")[0]))].filter(Boolean);
  useEffect(() => void paths.forEach((p) => loadFile(p)), [paths.join("|"), data.events_count]); // eslint-disable-line react-hooks/exhaustive-deps
  const regions = paths.flatMap((p) => (files[p]?.regions || []).filter((r) => !lane || r.lane === lane.lane).map((r) => ({ ...r, path: p, base: files[p].base })));
  if (!regions.length) return <p className="muted">{paths.length ? "Nothing written yet: a unit shows here once its lane writes it." : "This lane owns no unit of the goal's files."}</p>;
  return (
    <div className="rp-diff mono" data-testid="run-page-diff-rows">
      {regions.map((r) => (
        <section key={r.key} className="rp-unit" data-state={r.state}>
          <div className="rp-unit-head">{r.key} · lane {r.lane} · {r.state}</div>
          {r.base.slice(r.start_line - 1, r.end_line).map((ln, i) => <div key={"b" + i} className="rp-del">- {ln}</div>)}
          {r.text.map((ln, i) => <div key={"t" + i} className="rp-add">+ {ln}</div>)}
        </section>
      ))}
    </div>
  );
}

export function TestPage({ data, lane }: { data: RunPayload; lane: Lane | null }) {
  const events = useOrch((s) => s.events);
  const gate = events.filter((e) => e.kind === "gate" && (!lane || e.lane === lane.lane)).slice(-12);
  const r = data.report;
  return (
    <div className="rp-test" data-testid="run-page-test-rows">
      <p className="mono muted">the gate: {data.goal.test || "the lineup's test, if it names one"} · done when: {short(data.goal.done_when, 120)}</p>
      {lane?.rebased && <p className="mono">re-based on {lane.rebased.onto.map((o) => `lane ${o.lane}`).join(", ")}: tests {lane.rebased.tests_ok ? "pass" : "do not pass"}</p>}
      {lane?.pieces_returned ? <p className="mono">the gate sent this lane back {lane.pieces_returned}x (cap {data.goal.return_cap})</p> : null}
      {gate.length ? <ul className="rp-list mono">{gate.map((e, i) => <li key={i}>{elapsed(e.elapsed_s)} · {e.text}</li>)}</ul> : <p className="muted">The gate has not run{lane ? " on this lane" : ""} yet.</p>}
      {r && <p className="mono" data-ok={String(r.tests_ok)}>finished branch: tests {r.tests_ok ? "pass" : "do not pass"}</p>}
      {r?.tests_tail && <pre className="rr-tail mono">{r.tests_tail}</pre>}
    </div>
  );
}

export function LogPage({ lane }: { lane: Lane | null }) {
  const events = useOrch((s) => s.events);
  const rows = events.filter((e) => !lane || e.lane === lane.lane).slice(-80);
  if (!rows.length) return <p className="muted">No line yet.</p>;
  return (
    <ul className="rp-log mono" data-testid="run-page-log-rows">
      {rows.map((e, i) => <li key={i} data-kind={e.kind}><span className="muted">+{elapsed(e.elapsed_s)}</span> <span className="rp-k">{e.kind}</span> {e.lane ? `lane ${e.lane} · ` : ""}{e.text}</li>)}
    </ul>
  );
}
