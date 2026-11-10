// A block's When page (3.3.16.3, the owner: "add this workflow in there when this situation happens"): the rule its line
// carries, on one page, four choices in plain words -- when main needs (pdf, images, audio, video, code, a plan,
// research, a review, work data), or when the task says (words), or only when asked by name, or always first (before
// main answers) -- and Disconnect (main never uses it: the block stays, dashed). It writes the lineup's `workflows:`
// item, or config `workflows.when.<ref>` on the auto lineup; Save says which before it happens. Clicking the line opens
// it too. Undo walks it back.
import { useState } from "react";
import { Button } from "../../../lib/ui";
import { setWhen } from "../blocks/opsSquare";
import { writesBoard } from "../blocks/templates";
import { setPage, type Square } from "./store";
import { Head } from "./WorkflowSummary";

const NEEDS: [string, string][] = [["pdf", "pdf"], ["vision", "images"], ["audio", "audio"], ["video", "video"], ["code", "code"],
  ["plan", "a plan"], ["research", "research"], ["review", "a review"], ["work-data", "work data"]];
type Mode = "needs" | "words" | "named" | "always";
const MODES: [Mode, string][] = [["needs", "When main needs"], ["words", "When the task says"], ["named", "Only when asked by name"], ["always", "Always first, before main answers"]];

function first(q: Square): Mode {
  const w = q.when || {};
  return w.mode === "named" ? "named" : w.mode === "always" ? "always" : (w.words || []).length && !(w.needs || []).length ? "words" : "needs";
}

export function WhenPage({ q }: { q: Square }) {
  const w = q.when || {};
  const [mode, setMode] = useState<Mode>(first(q));
  const [needs, setNeeds] = useState<string[]>((w.needs || []).length ? w.needs! : q.covers.filter((c) => c !== "media"));
  const [words, setWords] = useState((w.words || []).join(", "));
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const off = q.when_mode === "off";
  const list = words.split(/[,\s]+/).map((x) => x.trim().toLowerCase()).filter(Boolean);
  const plainNeeds = needs.length && [...needs].sort().join() === q.covers.filter((c) => c !== "media").sort().join();
  const body = mode === "named" || mode === "always" ? { mode } : mode === "words" ? { words: list } : plainNeeds ? {} : { needs };
  const empty = (mode === "needs" && !needs.length) || (mode === "words" && !list.length);
  const run = async (when: object, label: string) => {
    setBusy(true);
    try {
      await setWhen(q.ref, when, label);
      setErr("");
      setPage("summary");
    } catch (e) {
      setErr((e as Error).message || "not saved");
    } finally {
      setBusy(false);
    }
  };
  const tick = (n: string) => setNeeds(needs.includes(n) ? needs.filter((x) => x !== n) : [...needs, n]);
  return (
    <div className="wf-page blk-when" data-testid="wf-page-when">
      <Head q={q} title="When main uses it" />
      <p className="muted">{off ? "Not connected: main never uses this block. Pick when it should, then Save to draw its line." : q.when_sentence || "main hands it work when it needs what it covers"}</p>
      <div className="blk-when-modes" role="radiogroup" aria-label={`When main hands ${q.ref} work`}>
        {MODES.map(([m, label]) => (
          <div key={m} className="blk-when-mode" data-on={mode === m || undefined}>
            <label className="blk-when-pick" data-density="row">
              <input type="radio" name={`when-${q.ref}`} checked={mode === m} onChange={() => setMode(m)} data-testid="wf-when-mode" data-mode={m} />
              <span>{label}</span>
            </label>
            {m === "needs" && mode === "needs" && (
              <div className="blk-when-needs">
                {NEEDS.map(([n, word]) => (
                  <label key={n} className="blk-when-need" data-density="row">
                    <input type="checkbox" checked={needs.includes(n)} onChange={() => tick(n)} data-testid="wf-when-need" data-need={n} />
                    <span>{word}</span>
                  </label>
                ))}
              </div>
            )}
            {m === "words" && mode === "words" && (
              <input className="input mono blk-when-words" value={words} onChange={(e) => setWords(e.target.value)} placeholder="review, audit"
                     aria-label="The words that send the task to this block" data-testid="wf-when-words" />
            )}
          </div>
        ))}
      </div>
      {err && <p className="wf-err" data-testid="wf-page-error">{err}</p>}
      <p className="muted mono blk-when-writes">writes {writesBoard().replace("workflows.enabled", `workflows.when.${q.ref}`).replace("its workflows: list", `its workflows: item for ${q.ref}`)}</p>
      <div className="wf-page-actions" data-density="bar">
        <Button variant="primary" size="sm" disabled={busy || empty} onClick={() => void run(body, "when changed")} data-testid="wf-when-save">Save</Button>
        {!off && <Button size="sm" variant="ghost" disabled={busy} onClick={() => void run({ mode: "off" }, "disconnected")} data-testid="wf-when-disconnect"
                         title="main never uses it; the block stays on the canvas, dashed">Disconnect</Button>}
      </div>
    </div>
  );
}
