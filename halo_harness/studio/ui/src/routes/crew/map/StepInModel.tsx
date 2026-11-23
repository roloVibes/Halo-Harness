// The MODEL block in the step-in sheet's body (3.6.0.15 O2-5, "the box acts"; the owner, 2026-11-18: the Live card lets
// him act, edit an agent, set its model; 2026-11-12: models are picked, never typed). ONE `GET crew/agent-model` at the
// click (studio/crew_model_api.py) says what a pick does for THIS kind of helper; the sheet opens when it and Last said
// have answered, or at 1 s (modelBlock.ts sheetReady). Drawn on a member's sheet and on main's only (the coordinator's
// ruling F). The shared picker folds IN PLACE (a dialog in document.body would be "outside" and fold the sheet); a pick
// POSTs crew/agent-model (his agent saved, or one made, through the Agents form's own routes; main's through /model),
// its answer's line replaces the rows, and [Undo] sends its token back. [Edit in Agents] opens his agent in the form;
// [Make it an agent] is the face's "Save as an agent" (LitBits.tsx saveAsAgent). When the sheet goes, the timer is
// cleared and every request of the block aborted and its answer dropped (a save already sent stays saved); no interval.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, call } from "../../../lib/api";
import { goSection } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { ModelSelect } from "../../shared/ModelSelect";
import { AUTO } from "../Form";
import { openAgent } from "../store";
import { saveAsAgent } from "./LitBits";
import { blockParts, refusedLine, type After, type ModelAnswer, type ModelGot } from "./modelBlock";
import { SAID_WAIT_MS, saidOpen } from "./sheetPlace";

/** `got`: null (no block on this sheet), "reading", the answer or its error; `ready`: the sheet may open. */
export function useModel(sid: string, aid: string | null): { got: ModelGot | null; ready: boolean } {
  const [got, setGot] = useState<ModelGot | null>(aid ? "reading" : null);
  const [waited, setWaited] = useState(0);
  useEffect(() => { // once, at the click
    if (!aid) return;
    let dropped = false;
    const ctl = new AbortController();
    const timer = setTimeout(() => setWaited(SAID_WAIT_MS), SAID_WAIT_MS);
    api.get<ModelAnswer>("crew/agent-model", { session: sid, agent: aid }, ctl.signal)
      .then((r) => dropped || setGot(r), (e) => dropped || setGot({ error: e instanceof Error ? e.message : String(e) }))
      .finally(() => clearTimeout(timer));
    return () => { dropped = true; clearTimeout(timer); ctl.abort(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return { got, ready: !aid || saidOpen(got !== "reading", waited) };
}

type Answer = { line?: string; undo?: unknown };

/** `late`: the answer came after the sheet opened, so the block sits at the body's end. */
export function StepInModel({ sid, aid, got, late }: { sid: string; aid: string; got: ModelGot; late?: boolean }) {
  const [after, setAfter] = useState<After | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = useRef<AbortController | null>(null);
  useEffect(() => () => { live.current?.abort(); live.current = null; }, []); // the sheet went: drop what is in flight
  const parts = blockParts(got, after);
  if (!parts) return null;
  const info = got !== "reading" && !("error" in got) ? got : null;
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
  const refused = (e: unknown) => (e instanceof ApiError ? refusedLine(e.data, e.message) : refusedLine(undefined, String(e)));
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
            (e) => end(ctl, { line: refused(e), undo: null }));
  };
  const edit = () => void openAgent(info?.name || "").then(() => goSection("agents", "crew"));
  const make = () => void saveAsAgent(sid, aid).then((ok) => { if (ok) goSection("agents", "crew"); });
  return (
    <div className="mp-step-in-model" data-testid="map-step-in-model" data-kind={info?.kind} data-late={late || undefined}>
      <b className="mp-step-in-model-head">{parts.heading}</b>
      {parts.first && <p className="mp-step-in-state mono" data-testid="map-step-in-model-first">{parts.first}</p>}
      {parts.picker && info && (
        <ModelSelect label={parts.label} value={picked ?? info.model} onPick={pick} testid="map-step-in-model-select"
                     inherit={info.kind === "MAIN" ? undefined : AUTO} inline compact noTest busy={busy} />
      )}
      <div className="mp-step-in-model-lines" data-testid="map-step-in-model-line">
        {parts.rows.map((r, i) => <p key={i} className="mp-step-in-state mono">{r}</p>)}
      </div>
      {(parts.undo || parts.edit || parts.make) && (
        <div className="mp-step-in-model-btns">
          {parts.undo && <Button size="sm" data-testid="map-step-in-model-undo" disabled={busy} onClick={undo}>{parts.undo}</Button>}
          {parts.edit && <Button size="sm" data-testid="map-step-in-model-edit" onClick={edit}>{parts.edit}</Button>}
          {parts.make && <Button size="sm" data-testid="map-step-in-model-make" onClick={make}>{parts.make}</Button>}
        </div>
      )}
    </div>
  );
}
