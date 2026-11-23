// The MODEL block in the step-in sheet's body (3.6.0.15 O2-5, "the box acts"; the owner, 2026-11-18: the Live card lets
// him act, edit an agent, set its model; 2026-11-12: models are picked, never typed). O2-8: it is CLOSED until asked for
// (the owner's rule: a section he uses rarely is closed by default, opened by its button, and has a close button): the
// body's first child is ONE row, "MODEL" and [Change]; a press opens the block in place under the row and, the first
// time in this sheet's life, sends the ONE `GET crew/agent-model` (studio/crew_model_api.py: what a pick does for THIS
// kind of helper); [Close] takes it out of the page and keeps what it held. Drawn on a member's sheet and on main's only
// (the coordinator's ruling F). The shared picker folds IN PLACE (a dialog in document.body would be "outside" and fold
// the sheet); a pick POSTs crew/agent-model (his agent saved, or one made, through the Agents form's own routes; main's
// through /model), its answer's line replaces the rows, and [Undo] sends its token back. [Edit in Agents] opens his agent
// in the form; [Make it an agent] is the face's "Save as an agent" (LitBits.tsx saveAsAgent). When the sheet goes, every
// request of the block is aborted and its answer dropped (a save already sent stays saved); no timer, no interval.
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { api, ApiError, call } from "../../../lib/api";
import { goSection } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { ModelSelect } from "../../shared/ModelSelect";
import { AUTO } from "../Form";
import { openAgent } from "../store";
import { saveAsAgent } from "./LitBits";
import { blockParts, refusedLine, toggleParts, type After, type ModelAnswer, type ModelGot } from "./modelBlock";

/** `got`: null until `ask()` (the block's first open), then "reading", the answer or its error. */
export function useModel(sid: string, aid: string): { got: ModelGot | null; ask: () => void } {
  const [got, setGot] = useState<ModelGot | null>(null);
  const live = useRef<AbortController | null>(null);
  useEffect(() => () => live.current?.abort(), []); // the sheet went: the read is aborted and its answer dropped
  const ask = () => {
    if (live.current) return; // asked once in this sheet's life: a second open asks nothing more
    const ctl = new AbortController();
    live.current = ctl;
    setGot("reading");
    api.get<ModelAnswer>("crew/agent-model", { session: sid, agent: aid }, ctl.signal)
      .then((r) => ctl.signal.aborted || setGot(r), (e) => ctl.signal.aborted || setGot({ error: e instanceof Error ? e.message : String(e) }));
  };
  return { got, ask };
}

type Answer = { line?: string; undo?: unknown };

export function StepInModel({ sid, aid }: { sid: string; aid: string }) {
  const [open, setOpen] = useState(false); // a sheet opened anew starts closed
  const { got, ask } = useModel(sid, aid);
  const [after, setAfter] = useState<After | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = useRef<AbortController | null>(null);
  useEffect(() => () => { live.current?.abort(); live.current = null; }, []); // the sheet went: drop what is in flight
  const id = useId();
  const lines = useRef<HTMLDivElement>(null);
  const held = useRef(0); // the rows' height at THEIR first draw (the answer's): a pick's shorter line moves nothing under them
  useLayoutEffect(() => { if (!held.current && lines.current && got && got !== "reading") held.current = lines.current.offsetHeight; });
  const tp = toggleParts(open);
  const toggle = () => {
    if (!open) ask();
    setOpen(!open);
  };
  const parts = got ? blockParts(got, after) : null;
  const info = got && got !== "reading" && !("error" in got) ? got : null;
  const start = () => {
    live.current?.abort();
    const ctl = new AbortController();
    live.current = ctl;
    setBusy(true);
    return ctl;
  };
  const end = (ctl: AbortController, next: After) => {
    if (ctl.signal.aborted) return; // dropped: the sheet went, or a newer request took its place
    setAfter(next);
    setBusy(false);
  };
  const refused = (e: unknown, isUndo = false) =>
    (e instanceof ApiError ? refusedLine(e.data, e.message, isUndo) : refusedLine(undefined, String(e), isUndo));
  const pick = (choice: string) => {
    const ref = choice || (info?.kind === "MAIN" ? "" : "auto");
    if (!ref) return;
    const ctl = start();
    call<Answer>("POST", "crew/agent-model", { session: sid, agent: aid, model: ref }, undefined, ctl.signal)
      .then((r) => { if (!ctl.signal.aborted) setPicked(choice); end(ctl, { line: String(r?.line || ""), undo: r?.undo ?? null }); },
            (e) => end(ctl, { line: refused(e), undo: null }));
  };
  const undo = () => {
    const ctl = start();
    call<Answer>("POST", "crew/agent-model/undo", { undo: after?.undo }, undefined, ctl.signal)
      .then((r) => { if (!ctl.signal.aborted) setPicked(null); end(ctl, { line: String(r?.line || ""), undo: null }); },
            (e) => end(ctl, { line: refused(e, true), undo: null }));
  };
  const edit = () => void openAgent(info?.name || "").then(() => goSection("agents", "crew"));
  const make = () => void saveAsAgent(sid, aid).then((ok) => { if (ok) goSection("agents", "crew"); });
  return (
    <>
      <div className="mp-step-in-model" data-testid="map-step-in-model">
        <b className="mp-step-in-model-head">MODEL</b>
        <Button size="sm" data-testid="map-step-in-model-toggle" aria-expanded={tp.expanded} aria-controls={id} onClick={toggle}>{tp.word}</Button>
      </div>
      {open && parts && (
        <div id={id} className="mp-step-in-model-open" data-testid="map-step-in-model-content" data-kind={info?.kind}>
          {parts.first && <p className="mp-step-in-state mono" data-testid="map-step-in-model-first">{parts.first}</p>}
          {parts.picker && info && (
            <ModelSelect label={parts.label} value={picked ?? info.model} onPick={pick} testid="map-step-in-model-select"
                         inherit={info.kind === "MAIN" ? undefined : AUTO} inline compact noTest busy={busy} />
          )}
          <div ref={lines} className="mp-step-in-model-lines" data-testid="map-step-in-model-line" style={held.current ? { minHeight: held.current } : undefined}>
            {parts.rows.map((r, i) => <p key={i} className="mp-step-in-state mono">{r}</p>)}
          </div>
          {parts.btns && (
            <div className="mp-step-in-model-btns">
              {parts.undo ? <Button size="sm" data-testid="map-step-in-model-undo" disabled={busy} onClick={undo}>{parts.undo}</Button>
                : parts.undoRoom && <Button size="sm" className="mp-step-in-model-held" disabled tabIndex={-1} aria-hidden>Undo</Button>}
              {parts.edit && <Button size="sm" data-testid="map-step-in-model-edit" onClick={edit}>{parts.edit}</Button>}
              {parts.make && <Button size="sm" data-testid="map-step-in-model-make" onClick={make}>{parts.make}</Button>}
            </div>
          )}
        </div>
      )}
    </>
  );
}
