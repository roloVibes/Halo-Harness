// Local -> Hugging Face (3.3.5.0 R5): the huggingface.model_dirs folders (Add folder, Forget) and, per folder, what is
// on disk (HfRow.tsx: Serve, Stop, Log, Delete, Use as default), a download stopped part-way, the host the fit is
// worked out on and the window, and the Jobs list (the downloads running, each with Cancel). GET local/hf/dirs, again
// every 30 s while the page is open (a server's readiness, a download from a terminal). A download starts from a
// Library hub row (its Download: the licence card first); `halo local download` does the same from a terminal.
import { useEffect, useState } from "react";
import { Button, Empty } from "../../lib/ui";
import { HfCards } from "./HfCards";
import { HfRow } from "./HfRow";
import { addFolder, forgetFolder, loadDirs, pick, useHf } from "./hfstore";
import { startJobs } from "./jobs";
import { gb, WINDOWS } from "./libstore";
import { goto } from "./pages";
import { JobsList } from "./Pulls";
import type { HfDir } from "./types";

const REFRESH_MS = 30_000;

function Folder({ d }: { d: HfDir }) {
  const busy = useHf((s) => s.busy);
  const said = useHf((s) => s.said[`forget|${d.path}`]);
  return (
    <section className="lc-block lc-hf-dir" aria-label={d.path} data-testid="local-hf-dir" data-path={d.path} data-exists={d.exists ? "yes" : "no"}>
      <div className="lc-hf-dir-head">
        <span className="rail-label mono">{d.path}</span>
        <span className="mono muted" title="the models' files on disk, summed">{d.models.length} model{d.models.length === 1 ? "" : "s"} · {gb(d.size)}</span>
        {!d.exists && <span className="lc-why">not there</span>}
        <span className="spacer" />
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => void forgetFolder(d.path)} data-testid="local-hf-forget"
                title={`halo local forget ${d.path} (the folder stays on disk)`}>Forget</Button>
        {said && <span className="mono lc-said" data-ok={said.ok || undefined}>{said.text}</span>}
      </div>
      {d.models.length > 0 && <ul className="lc-model-list">{d.models.map((m) => <HfRow key={m.key} m={m} />)}</ul>}
      {d.partial.map((p) => (
        <p key={p.repo} className="mono muted" data-testid="local-hf-partial" title="its .part files in blobs/: Download again resumes from them">
          {p.repo}: stopped part-way, {gb(p.bytes)} kept
        </p>
      ))}
      {!d.models.length && !d.partial.length && d.exists && (
        <p className="muted">Nothing here yet: download a repo from <Button size="sm" variant="ghost" onClick={() => goto("library")} data-testid="local-hf-to-library">Library</Button> (a Hugging Face row's Download), or halo local download &lt;repo&gt;.</p>
      )}
    </section>
  );
}

function AddFolder() {
  const [path, setPath] = useState("");
  const busy = useHf((s) => s.busy);
  const said = useHf((s) => s.said.folder);
  return (
    <div className="lc-pull-name" data-testid="local-hf-add-box">
      <input className="input mono" value={path} onChange={(e) => setPath(e.target.value)} placeholder="a folder for models: /data/models"
             aria-label="add a model folder" data-testid="local-hf-add-path" onKeyDown={(e) => e.key === "Enter" && path.trim() && void addFolder(path.trim())} />
      <Button size="sm" disabled={busy || !path.trim()} onClick={() => void addFolder(path.trim())} data-testid="local-hf-add"
              title={path.trim() ? `halo local add ${path.trim()}` : "type a folder's path"}>Add folder</Button>
      {said && <span className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-hf-add-said">{said.text}</span>}
    </div>
  );
}

function Picks() {
  const data = useHf((s) => s.data);
  const host = useHf((s) => s.host);
  const win = useHf((s) => s.window);
  return (
    <div className="lc-hf-pick" data-testid="local-hf-picks">
      <label className="mono muted" title="the fit meter is worked out on this host's hardware card">fit on{" "}
        <select value={host || data?.host || ""} onChange={(e) => pick({ host: e.target.value })} data-testid="local-hf-host">
          {(data?.hosts || []).map((h) => <option key={h.name} value={h.name} disabled={!h.card}>{h.name}{h.here ? " (this machine)" : ""}{h.card ? "" : " (no card yet)"}</option>)}
        </select>
      </label>
      <label className="mono muted">at{" "}
        <select value={win || data?.window || ""} onChange={(e) => pick({ window: Number(e.target.value) || null })} data-testid="local-hf-window">
          {WINDOWS.map((w) => <option key={w} value={w}>{w.toLocaleString("en-US")}</option>)}
        </select>
      </label>
    </div>
  );
}

export function HfPage() {
  const data = useHf((s) => s.data);
  const error = useHf((s) => s.error);
  useEffect(() => {
    startJobs();
    void loadDirs();
    const id = window.setInterval(() => {
      if (!document.hidden) void loadDirs();
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="lc-models lc-hf" data-testid="local-hf">
      <Picks />
      <AddFolder />
      <JobsList />
      {!data ? (
        error ? <Empty title="Studio could not read the model folders" body={error} /> : <div className="mono muted">reading the model folders...</div>
      ) : data.dirs.length ? (
        data.dirs.map((d) => <Folder key={d.path} d={d} />)
      ) : (
        <Empty title="No model folder yet" body="Add a folder above (huggingface.model_dirs): downloads go there, and every .gguf file or model folder in it is listed." testid="local-hf-none" />
      )}
      <HfCards />
    </div>
  );
}
