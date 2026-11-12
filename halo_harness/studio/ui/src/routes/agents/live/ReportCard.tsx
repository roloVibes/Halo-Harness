// The run report card (3.4.1.0 R3 "Time"; docs/REPLAY.md "The report card"): one finished run -- a session, a goal run, a
// saved replay file made anywhere -- rendered from its record by live/report_card.py, never hand-written, no model call
// (cardData.ts reads it). Summary first: how it ended and R2's nine figures, then the story in about ten lines (who was
// asked what, what each handed back), where the time went (by phase, by block), where the money went (by model, by
// block), what failed and what happened next, what waited on you and for how long, which model did what, the files it
// wrote, and what this record cannot show (said in words, never a blank). Copy puts the same card's Markdown (`halo
// report`) on the clipboard. A session's or a file's card is a page of History (CardPage: its row's Report door, Live's
// row for the session that ended); a goal run's is the FIRST block of its report page (run/RunReport.tsx).
import type { ReactNode } from "react";
import { Button } from "../../../lib/ui";
import { short } from "../../orchestra/format";
import { closeReport, toggleHistory } from "./historyStore";
import { openFileReplay, openLiveReplay } from "./replay";
import { bare, copyMarkdown, pct, secs, usd, useCard, type Card } from "./cardData";

const FIGURES: [string, string][] = [["ended", "How it ended"], ["wall", "Wall time"], ["cost", "Cost"], ["tokens", "Tokens"], ["models", "Models used"],
  ["agents", "Agents spawned"], ["asks", "Asks to you"], ["failures", "Failures"], ["retries", "Retries"]];

function Part({ k, title, children }: { k: string; title: string; children: ReactNode }) {
  return (
    <section className="rr-block rcd-part" data-testid="report-card-section" data-key={k}>
      <div className="rail-label mono">{title}</div>
      {children}
    </section>
  );
}

function Share({ share }: { share: number | null }) {
  return <span className="rcd-bar" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(1, share || 0)) * 100}%` }} /></span>;
}

function Time({ c }: { c: Card }) {
  const t = c.time;
  return (
    <Part k="time" title="WHERE THE TIME WENT">
      <p className="mono muted">wall time {secs(t.wall_s)} · by phase, then by block (agent time: agents overlap)</p>
      {t.phases.length ? (
        <ul className="rcd-rows mono">{t.phases.map((p) => (
          <li key={p.phase} className="rcd-row" data-phase={p.phase} title={`${p.words}: ${secs(p.secs)}, ${pct(p.share)} of the wall time`}>
            <span className="rcd-k">{p.words}</span><Share share={p.share} /><span>{secs(p.secs)} · {pct(p.share)}</span>
          </li>))}</ul>
      ) : <p className="muted">By phase: not in this record.</p>}
      <ul className="rcd-list">{t.blocks.map((b) => (
        <li key={b.block}><b className="mono">{b.block}</b> {b.agents} agent{b.agents === 1 ? "" : "s"}, {secs(b.secs)} of agent time ({secs(b.busy)} busy)</li>))}</ul>
    </Part>
  );
}

function Money({ c }: { c: Card }) {
  const m = c.money;
  const total = m.total === null || (!m.known && !m.total) ? "unknown" : usd(m.total, !m.known);
  return (
    <Part k="money" title="WHERE THE MONEY WENT">
      <p className="mono">total {total}</p>
      <ul className="rcd-rows mono">{m.models.map((x) => (
        <li key={x.model} className="rcd-row" data-unknown={x.unknown || undefined} title={x.model}>
          <span className="rcd-k">{bare(x.model)}</span><Share share={x.unknown ? null : x.share} /><span>{usd(x.cost_usd, x.unknown)}{x.unknown ? "" : ` · ${pct(x.share)}`}</span>
        </li>))}</ul>
      {!m.models.length && <p className="muted">By model: nothing priced in this record.</p>}
      {!!m.blocks.length && <p className="mono muted">by block: {m.blocks.map((b) => `${b.block} ${usd(b.cost_usd, b.unknown)}`).join(" · ")}{m.known ? "" : " (priced calls only: an unpriced call is in no block)"}</p>}
    </Part>
  );
}

function Failed({ c }: { c: Card }) {
  const none = !c.failures.length && !c.failed_calls && !c.retries;
  return (
    <Part k="failures" title="WHAT FAILED AND WHAT HAPPENED NEXT">
      <ul className="rcd-list">
        {c.failures.map((f, i) => <li key={i} data-testid="report-card-fail"><span className="mono rcd-at">{f.at}</span> {f.who} failed; next: {f.next}</li>)}
        {!!c.failed_calls && <li>{c.failed_calls} model call{c.failed_calls === 1 ? "" : "s"} failed (the provider answered with an error)</li>}
        {!!c.retries && <li>{c.retries} retr{c.retries === 1 ? "y" : "ies"}{c.kind === "run" ? " (pieces the gate sent back)" : " by the provider"}</li>}
      </ul>
      {none && <p className="muted">Nothing failed.</p>}
    </Part>
  );
}

function Waited({ c }: { c: Card }) {
  const timed = c.waits.filter((w) => w.secs !== null);
  const total = !c.waits.length ? "Nothing waited on you." : !timed.length ? "How long these waited is not in the record."
    : `In all ${timed.length < c.waits.length ? "at least " : ""}${secs(c.waited_s)} waiting on you.`;
  return (
    <Part k="waits" title="WHAT WAITED ON YOU">
      <ul className="rcd-list">{c.waits.map((w, i) => (
        <li key={i} data-testid="report-card-wait" data-secs={w.secs ?? undefined}>
          <span className="mono rcd-at">{w.at}</span> {w.who}: {w.text}{w.secs !== null && !w.text.includes("answered") ? ` -- ${secs(w.secs)}` : ""}
        </li>))}</ul>
      <p className="muted">{total}</p>
    </Part>
  );
}

function Models({ c }: { c: Card }) {
  return (
    <Part k="models" title="WHICH MODEL DID WHAT">
      <ul className="rcd-list">{c.models.map((m) => (
        <li key={m.model} data-testid="report-card-model" data-model={m.model} title={m.model}>
          <b className="mono">{bare(m.model)}</b>
          {(m.cost_share !== null || m.time_share !== null) && <span className="mono muted"> · {pct(m.cost_share)} of cost, {pct(m.time_share)} of time</span>}
          <ul className="rcd-sub">{m.agents.map((a, i) => (
            <li key={i}>{a.name}{a.role && a.role !== a.name ? ` (${a.role})` : ""}{a.task ? `: ${short(a.task, 160)}` : ""}</li>))}</ul>
        </li>))}</ul>
    </Part>
  );
}

function Files({ c }: { c: Card }) {
  return (
    <Part k="artefacts" title="ARTEFACTS">
      {c.artefacts === null ? <p className="muted">Not in this record (said below).</p> : !c.artefacts.length ? <p className="muted">No file was written.</p> : (
        <ul className="rcd-list">{c.artefacts.map((a) => (
          <li key={a.rel} data-testid="report-card-art" data-rel={a.rel}>
            <span className="mono">{a.rel}</span>{a.outside ? <span className="muted"> (outside the project: its name only)</span> : null}
            <span className="muted"> -- {a.by.join(", ")}</span>
          </li>))}</ul>
      )}
    </Part>
  );
}

/** The card of `refId` (session:<id> | run:<id> | file:<id>): its figures and sections, with Copy. */
export function ReportCard({ refId }: { refId: string }) {
  const { card: c, markdown, error } = useCard(refId);
  return (
    <div className="rcd" data-testid="report-card" data-ref={refId} data-state={error ? "error" : c ? "ready" : "reading"} data-kind={c?.kind}>
      <div className="rcd-head" data-density="bar">
        <span className="glance-kicker mono">REPORT CARD</span>
        <span className="mono muted rcd-from">{c?.file ? `from the saved replay ${c.file}` : "from the record"} · no model call</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" disabled={!markdown} onClick={() => copyMarkdown(markdown)} data-testid="report-card-copy"
                title="The card as Markdown on the clipboard: the same text halo report prints (nothing written)">Copy Markdown</Button>
      </div>
      {error ? <p className="field-error" data-testid="report-card-error">{error}</p> : !c ? <p className="mono muted">reading the record...</p> : (
        <>
          <dl className="rcd-figures mono" data-testid="report-card-figures">
            {FIGURES.map(([k, label]) => c.cells[k] && (
              <div key={k} className="rcd-fig" data-testid="report-card-figure" data-key={k} data-unknown={c.cells[k].unknown || undefined} title={`${label}: ${c.cells[k].text}`}>
                <dt>{label}</dt><dd>{c.cells[k].text}</dd>
              </div>))}
          </dl>
          <Part k="story" title="THE STORY">
            <ol className="rcd-story" data-testid="report-card-story">{c.story.map((s, i) => (
              <li key={i} data-testid="report-card-step" data-kind={s.kind} data-t={s.t}><span className="mono rcd-at">{s.at}</span> {s.text}</li>))}</ol>
            {c.story_more > 0 && <p className="muted">...and {c.story_more} more step{c.story_more === 1 ? "" : "s"} (Replay shows every one).</p>}
          </Part>
          <Time c={c} />
          <Money c={c} />
          <Failed c={c} />
          <Waited c={c} />
          <Models c={c} />
          <Files c={c} />
          <Part k="cannot" title="WHAT THIS RECORD CANNOT SHOW">
            <ul className="rcd-list muted">{c.cannot.map((line, i) => <li key={i} data-testid="report-card-cannot">{line}</li>)}</ul>
          </Part>
        </>
      )}
    </div>
  );
}

/** History's page for a session's or a saved file's card: Back, Replay, then the card. */
export function CardPage({ refId, what }: { refId: string; what: string }) {
  const [kind, id] = [refId.split(":")[0], refId.slice(refId.indexOf(":") + 1)];
  const replay = () => (kind === "file" ? openFileReplay(id) : openLiveReplay("session", id, what)).then((ok) => ok && toggleHistory(false));
  return (
    <div className="rr" data-testid="history-card" data-ref={refId}>
      <div className="rr-head" data-density="bar">
        <Button size="sm" variant="ghost" onClick={closeReport} data-testid="report-card-back" title="Back to History's list">Back</Button>
        <b className="lh-title">Report card</b>
        <span className="rr-goal-inline" title={what}>{short(what, 90)}</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={() => void replay()} data-testid="report-card-replay" title="Draw it on Live as it ended (Back to now returns)">Replay</Button>
      </div>
      <ReportCard refId={refId} />
    </div>
  );
}
