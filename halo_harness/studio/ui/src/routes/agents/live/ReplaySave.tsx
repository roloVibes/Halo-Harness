// Save this run's replay and Export a clip (3.4.1.0 R1 "Time"), the scrubber's two writes. Each is a Dialog opened by
// its button (never on load) that says what the file holds and where it goes BEFORE anything is written (DOES / COSTS /
// WRITES): Save asks the server what the replay would hold (GET replays/plan) and writes one `.halo-replay` file under
// <state>/replays/ (POST replays/save); a clip is filmed from a saved replay -- a session not yet saved is saved first,
// said -- over the range From .. To at the scrubber's speed (GET / POST replays/<id>/clip) and written under
// <state>/replays/clips/. After each, the path it wrote and a Download. 3.4.1.0 R2: a goal run saves and films the same
// way (`{run: <id>}`: its lead and lanes from the run's record, live/replay_run.py); a mission is the fleet pack's.
// 3.4.1.0 R6: the clip's plan needs no Pillow; without it the dialog says so in one line with the install command and
// Export is off (only the encode needs it).
import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { toast } from "../../../lib/store";
import { Button, Dialog } from "../../../lib/ui";
import { download } from "../../fleet/extras";
import { openFileReplay, type LiveReplay } from "./replay";
import { mmss } from "./timeline";

type SavePlan = { id: string; path: string; bytes: number; includes: string[] };
type Saved = SavePlan & { ok: boolean };
type ClipPlan = { from: number; to: number; speed: number; frames: number; seconds: number; width: number; format: string; path: string; note: string;
  chrome: boolean; max_seconds: number; pillow: boolean; needs: string };
type Clip = ClipPlan & { ok: boolean; name: string; url: string; bytes: number };

const why = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const kb = (n: number) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1048576).toFixed(1)} MB`);
const secs = (v: string): number | null => {
  const p = v.trim().split(":").map(Number);
  return p.some((x) => !isFinite(x)) || !v.trim() ? null : p.reduce((a, x) => a * 60 + x, 0);
};

/** What Save names: a session (and the lineup whose blocks go in), or (3.4.1.0 R2) a goal run by its id. */
const what = (r: LiveReplay, lineup: string): Record<string, string> => (r.kind === "run" ? { run: r.id } : { session: r.sid, ...(lineup ? { lineup } : {}) });

function usePlan(r: LiveReplay, lineup: string): [SavePlan | null, string] {
  const [plan, setPlan] = useState<SavePlan | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (r.kind !== "session" && r.kind !== "run") return;
    api.get<SavePlan>("replays/plan", what(r, lineup)).then(setPlan).catch((e) => setErr(why(e)));
  }, [r.sid, r.id, r.kind, lineup]); // eslint-disable-line react-hooks/exhaustive-deps
  return [plan, err];
}

async function save(r: LiveReplay, lineup: string): Promise<Saved | null> {
  try {
    const got = await api.post<Saved>("replays/save", what(r, lineup));
    toast(`Saved the replay: ${got.path}`, "done", 6000);
    return got;
  } catch (e) {
    toast(`Not saved: ${why(e)}`, "error", 6000);
    return null;
  }
}

export function SaveDialog({ r, lineup, onClose }: { r: LiveReplay; lineup: string; onClose: () => void }) {
  const [plan, err] = usePlan(r, lineup);
  const [done, setDone] = useState<Saved | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async () => (setBusy(true), setDone(await save(r, lineup)), setBusy(false));
  const cost = plan && !done ? { does: r.kind === "run" ? `Saves the goal run "${r.title}" as one replay file: the lead and its lanes, each lane's states over time, the marks, the run's figures`
                                    : `Saves "${r.title}" as one replay file: its agents, their states over time, the marks, the lineup's blocks`,
                                  costs: "nothing: no model call", writes: `${plan.path} (about ${kb(plan.bytes)})` } : undefined;
  return (
    <Dialog open onClose={onClose} title="Save this run's replay" testid="replay-save-dialog" cost={cost}
            footer={done ? <><Button onClick={() => void download(`replays/${done.id}`, `${done.id}.halo-replay`)} data-testid="replay-save-download">Download</Button><Button variant="primary" onClick={onClose}>Done</Button></>
              : <><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!plan || busy} onClick={() => void go()} data-testid="replay-save-go">{busy ? "Saving..." : "Save"}</Button></>}>
      {err ? <p className="field-error">{err}</p> : !plan ? <p className="muted">reading what it would hold...</p> : done ? (
        <p data-testid="replay-save-done" data-path={done.path}>Wrote <span className="mono">{done.path}</span>. Open it on any machine: <span className="mono">halo replay open {done.id}.halo-replay</span>, or History's Open a file.</p>
      ) : (
        <ul className="scr-holds" data-testid="replay-save-holds">{plan.includes.map((l) => <li key={l}>{l}</li>)}</ul>
      )}
    </Dialog>
  );
}

export function ClipDialog({ r, lineup, onClose }: { r: LiveReplay; lineup: string; onClose: () => void }) {
  const [rid, setRid] = useState(r.kind === "file" ? r.id : "");
  const [savePlan, saveErr] = usePlan(r, lineup);
  const at = Math.round(r.t - r.tl.t0);
  const [from, setFrom] = useState("0:00");
  const [to, setTo] = useState(mmss(at > 0 ? at : r.tl.t1 - r.tl.t0));
  const [plan, setPlan] = useState<ClipPlan | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Clip | null>(null);
  useEffect(() => {
    if (!rid) return;
    const f = secs(from), t = secs(to);
    if (f === null || t === null) return setErr("From and To are seconds, or m:ss");
    // 3.4.1.0 R6: only the newest ask's answer lands. The speed moving as the saved file opens and a From typed just
    // after sent two asks; the older answering last left a plan (and so an Export) of a range the fields no longer say.
    let newest = true;
    api.get<ClipPlan>(`replays/${encodeURIComponent(rid)}/clip`, { from: String(f), to: String(t), speed: String(r.speed) })
      .then((p) => newest && (setPlan(p), setErr(""))).catch((e) => newest && (setPlan(null), setErr(why(e))));
    return () => { newest = false; };
  }, [rid, from, to, r.speed]);
  const saveFirst = async () => {
    setBusy(true);
    const got = await save(r, lineup);
    setBusy(false);
    if (got) (setRid(got.id), void openFileReplay(got.id, r.t));
  };
  const film = async () => {
    if (!plan) return;
    setBusy(true);
    try {
      setDone(await api.post<Clip>(`replays/${encodeURIComponent(rid)}/clip`, { from: plan.from, to: plan.to, speed: plan.speed }));
    } catch (e) {
      setErr(why(e));
    }
    setBusy(false);
  };
  const cost = !rid && savePlan ? { does: "A clip is filmed from a saved replay: Save writes it first, then the clip's range is offered", costs: "nothing: no model call", writes: savePlan.path }
    : plan && !done ? { does: `Films ${mmss(plan.from)} to ${mmss(plan.to)} at ${plan.speed}x: ${plan.frames} frames, ${plan.seconds} s, ${plan.width} px wide, ${plan.format.toUpperCase()} (at most ${plan.max_seconds} s)`,
                        costs: `nothing: no model call; a headless Chrome on this machine for about ${Math.ceil(plan.frames / 4)} s`, writes: plan.path } : undefined;
  return (
    <Dialog open onClose={onClose} title="Export a clip" testid="replay-clip-dialog" cost={cost}
            footer={done ? <><Button onClick={() => void download(done.url, done.name)} data-testid="replay-clip-download">Download</Button><Button variant="primary" onClick={onClose}>Done</Button></>
              : !rid ? <><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!savePlan || busy} onClick={() => void saveFirst()} data-testid="replay-clip-save">Save first</Button></>
              : <><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!plan || !plan.chrome || !plan.pillow || busy} onClick={() => void film()} data-testid="replay-clip-go">{busy ? "Filming..." : "Export"}</Button></>}>
      {saveErr && !rid ? <p className="field-error">{saveErr}</p> : null}
      {rid && !done && (
        <div className="scr-range-fields">
          <label>From <input className="input mono" value={from} onChange={(e) => setFrom(e.target.value)} data-testid="replay-clip-from" /></label>
          <label>To <input className="input mono" value={to} onChange={(e) => setTo(e.target.value)} data-testid="replay-clip-to" /></label>
          <span className="muted">at {r.speed}x (the scrubber's speed)</span>
        </div>
      )}
      {err && <p className="field-error" data-testid="replay-clip-error">{err}</p>}
      {plan && !plan.chrome && !done && <p className="field-error">No Chrome found on this machine: install Chrome or set HALO_CHROME.</p>}
      {plan && !plan.pillow && !done && <p className="field-error" data-testid="replay-clip-needs">{plan.needs[0].toUpperCase() + plan.needs.slice(1)}.</p>}
      {plan?.note && !done && <p className="muted">{plan.note}.</p>}
      {done && <p data-testid="replay-clip-done" data-path={done.path}>Wrote <span className="mono">{done.path}</span> ({kb(done.bytes)}, {done.frames} frames).</p>}
    </Dialog>
  );
}
