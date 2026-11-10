// The board's inspector (3.3.16.0 R3), R1b's shape: summary first -- a `dl` of the whole contract in plain words --
// then one Edit row per block: Enable for this lineup, Budget, Limits, each its own page, and the YAML page for the
// file. It shows on hover or select, never on load. Delete on a card asks here (the `remove` page), never in a pop-up.
import { useState } from "react";
import { Button } from "../../../lib/ui";
import { disableSquare, enableSquare, saveContract, select, setPage, squareOf, useWf, type Page, type Square } from "./store";
import { YamlPage } from "./YamlPage";

const ROWS: [Page, string, (q: Square, on: boolean) => string][] = [
  ["enable", "Enable for this lineup", (_q, on) => (on ? "on: main may hand it work" : "off")],
  ["budget", "Budget", (q) => q.costs],
  ["limits", "Limits", (q) => q.limits],
  ["yaml", "YAML", (q) => q.path.split(/[\\/]/).slice(-2).join("/")],
];

function Lines({ q }: { q: Square }) {
  const lines: [string, string][] = [
    ["does", q.does || "-"], ["takes", q.takes.join(", ") || "text"], ["gives", q.gives.join(", ") || "- (not a square)"],
    ["covers", q.covers.join(", ") || "-"],
    ["lead", q.lead ? `${q.lead.bio} on ${q.lead.model || "the session's model"}` : typeof q.lineup === "string" ? `lineup ${q.lineup}` : "the session's lineup"],
    ["engine", q.engine === "mission" ? "mission (runs as orchestra while only this halo is here)" : q.engine],
    ["costs", q.costs], ["limits", q.limits], ["from", `${q.group} (${q.origin})`],
  ];
  return (
    <dl className="ri-summary wf-summary" data-testid="wf-summary">
      {lines.map(([k, v]) => (
        <div key={k} data-line={k}><dt className="mono">{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  );
}

function Head({ q, title }: { q: Square; title: string }) {
  return (
    <div className="wf-page-head" data-density="bar">
      <Button size="sm" variant="ghost" onClick={() => setPage("summary")} data-testid="wf-page-back">Back</Button>
      <b className="mono">{q.ref}</b><span className="muted">{title}</span>
    </div>
  );
}

function ReadOnly({ q }: { q: Square }) {
  return q.writable ? null : (
    <p className="muted wf-ro" data-testid="wf-read-only">{q.ref} is {q.origin} and read-only: copy it to yours first
      (<span className="mono">halo workflows new my-{q.ref.split("/").pop()} --from {q.ref}</span>), then edit the copy.</p>
  );
}

function FormPage({ q, kind }: { q: Square; kind: "budget" | "limits" }) {
  const [vals, setVals] = useState<Record<string, string>>(kind === "budget"
    ? { band: q.band, cap_usd: q.cap_usd == null ? "" : String(q.cap_usd) }
    : { depth: String(q.depth), turns: q.turns == null ? "" : String(q.turns), wall_s: q.wall_s == null ? "" : String(q.wall_s) });
  const [err, setErr] = useState("");
  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  const save = async () => {
    const body = kind === "budget" ? { budget: { band: vals.band, cap_usd: num(vals.cap_usd) } }
      : { limits: { depth: num(vals.depth), turns: num(vals.turns), wall_s: num(vals.wall_s) } };
    setErr(await saveContract(q.ref, body));
  };
  const help: Record<string, string> = {
    band: "low | mid | high: the router prefers the square nearest the session's band",
    cap_usd: "dollars one hand-off may spend; empty = no cap of its own (the session's budget still holds)",
    depth: "1 = it calls no square; 2 = it may hand off once more", turns: "model calls before it is stopped",
    wall_s: "seconds before it is stopped",
  };
  return (
    <div className="wf-page" data-testid={`wf-page-${kind}`}>
      <Head q={q} title={kind === "budget" ? "Budget" : "Limits"} />
      <ReadOnly q={q} />
      {Object.keys(vals).map((k) => (
        <label key={k} className="wf-field" data-density="row">
          <span className="mono">{k}</span>
          {k === "band" ? (
            <select value={vals[k]} disabled={!q.writable} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} data-testid={`wf-field-${k}`}>
              {["low", "mid", "high"].map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          ) : (
            <input value={vals[k]} disabled={!q.writable} inputMode="decimal" onChange={(e) => setVals({ ...vals, [k]: e.target.value })} data-testid={`wf-field-${k}`} />
          )}
          <small className="muted">{help[k]}</small>
        </label>
      ))}
      {err && <p className="wf-err" data-testid="wf-page-error">{err}</p>}
      <div className="wf-page-actions" data-density="bar">
        <Button variant="primary" size="sm" disabled={!q.writable} onClick={() => void save()} data-testid="wf-page-save">Save</Button>
      </div>
    </div>
  );
}

function EnablePage({ q, on, remove }: { q: Square; on: boolean; remove: boolean }) {
  const where = useWf((s) => s.board?.where || "this lineup");
  return (
    <div className="wf-page" data-testid={remove ? "wf-page-remove" : "wf-page-enable"}>
      <Head q={q} title={remove ? "Take it off the board" : "Enable for this lineup"} />
      <p>{on ? `${q.ref} is on for ${where}: main may hand it work.` : `${q.ref} is off for ${where}.`}</p>
      {remove && <p className="muted">Taking it off disables it for {where}; the file stays where it is.</p>}
      <div className="wf-page-actions" data-density="bar">
        {on ? <Button variant={remove ? "danger" : "default"} size="sm" onClick={() => void disableSquare(q.ref)} data-testid="wf-disable">Disable</Button>
          : <Button variant="primary" size="sm" onClick={() => void enableSquare(q.ref)} data-testid="wf-enable" disabled={!q.square}>Enable</Button>}
      </div>
    </div>
  );
}

export function WorkflowSummary() {
  const ref = useWf((s) => s.selected || s.hover);
  const q = useWf((s) => squareOf(s, s.selected || s.hover));
  const page = useWf((s) => (s.selected ? s.page : "summary"));
  const on = useWf((s) => !!s.board?.enabled.includes(ref));
  const selected = useWf((s) => !!s.selected);
  if (!q) return null;
  return (
    <aside className="wf-inspector" data-testid="wf-inspector" data-ref={q.ref} data-page={page} data-hover={!selected || undefined}>
      {page === "summary" && (
        <div className="ri-sum">
          <div className="wf-page-head" data-density="bar"><b className="mono">{q.ref}</b><span className="muted">{q.line.split(" · ")[3] || ""}</span></div>
          <Lines q={q} />
          <ul className="ri-rows" aria-label="Edit one block">
            {ROWS.map(([p, title, state]) => (
              <li key={p} className="ri-row" data-density="row" data-block={p}>
                <button className="ri-row-main" onClick={() => select(q.ref, p)} data-testid={`wf-block-${p}`}>
                  <span className="ri-row-title">{title}</span><span className="ri-row-state mono">{state(q, on)}</span>
                </button>
                <Button size="sm" variant="ghost" onClick={() => select(q.ref, p)} data-testid={`wf-edit-${p}`} aria-label={`Edit ${title}`}>Edit</Button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {(page === "enable" || page === "remove") && <EnablePage q={q} on={on} remove={page === "remove"} />}
      {(page === "budget" || page === "limits") && <FormPage key={`${q.ref}-${page}`} q={q} kind={page} />}
      {page === "yaml" && <YamlPage q={q} />}
    </aside>
  );
}
