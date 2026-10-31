// The cards Local -> Hugging Face opens (3.3.5.0 R5; routes/local/hfstore.ts): Serve (the runtime, each flag and
// where it comes from -- the window and -ngl from the fit planner on this machine's card -- a port and keep, then
// Start), Delete (what names the model first; Delete anyway; nothing while a server Halo started serves it), Log (the
// tail of the server's log), and Download (the repo's licence line and the files before a byte moves, the folder
// picked, then Accept and download). Each ends with the `halo local` line that does the same.
import { Button, Dialog } from "../../lib/ui";
import { acceptDownload, close, deleteModel, openLog, openServe, setDlDir, setServe, startServe, useHf } from "./hfstore";
import { gb, WINDOWS } from "./libstore";

const FLAGS: [string, string][] = [["window", "-c"], ["ngl", "-ngl"], ["parallel", "-np"], ["kv_type", "--cache-type-k/v"],
  ["flash_attn", "--flash-attn"], ["num_predict", "-n"]];

function Said({ k }: { k: string }) {
  const s = useHf((st) => st.said[k]);
  return s ? <p className="mono lc-said" data-ok={s.ok || undefined} data-testid="local-hf-said">{s.text}</p> : null;
}

function Cli({ text }: { text: string }) {
  return text ? <code className="mono lc-cli-line" data-testid="local-hf-cli" title="the same from a terminal">{text}</code> : null;
}

function ServeCard() {
  const o = useHf((s) => (s.open?.act === "serve" ? s.open : null));
  const busy = useHf((s) => s.busy);
  const said = useHf((s) => (o ? s.said[`serve|${o.m.path}`] : undefined));
  if (!o) return null;
  const p = o.plan;
  const started = said?.ok;
  return (
    <div className="lc-act-body" data-testid="local-hf-serve-card">
      <p className="mono">{o.m.repo ? `${o.m.repo} ${o.m.file}` : o.m.path}</p>
      <div className="lc-hf-pick">
        <label className="mono muted">runtime{" "}
          <select value={o.runtime || p?.runtime || ""} onChange={(e) => void openServe(o.m, o.window, e.target.value)} data-testid="local-hf-serve-runtime">
            <option value="llama-server">llama-server</option>
            <option value="mlx">mlx_lm.server (a Mac)</option>
          </select>
        </label>
        <label className="mono muted">window{" "}
          <select value={o.window || ""} onChange={(e) => void openServe(o.m, Number(e.target.value) || null, o.runtime)} data-testid="local-hf-serve-window">
            <option value="">the planner's</option>
            {WINDOWS.map((w) => <option key={w} value={w}>{w.toLocaleString("en-US")}</option>)}
          </select>
        </label>
        <label className="mono muted">port{" "}
          <input className="input mono lc-hf-port" value={o.port} placeholder="free" onChange={(e) => setServe({ port: e.target.value })} data-testid="local-hf-serve-port" />
        </label>
        <label className="mono muted" title="keep it running after the last Halo process on this home exits">
          <input type="checkbox" checked={o.keep} onChange={(e) => setServe({ keep: e.target.checked })} data-testid="local-hf-serve-keep" /> keep
        </label>
      </div>
      {!p ? <p className="mono muted">working out the flags…</p> : (
        <dl className="lc-facts" data-testid="local-hf-serve-flags">
          {FLAGS.map(([k, flag]) => {
            const v = (p.flags as Record<string, unknown>)[k];
            const shown = v === true ? "on" : v == null || v === false ? "-" : typeof v === "number" ? v.toLocaleString("en-US") : String(v);
            return (
              <div key={k} data-testid="local-hf-flag" data-flag={k} data-value={v == null ? "" : String(v)} title={p.sources[k] || ""}>
                <dt className="mono">{flag} {shown}</dt><dd className="muted">{p.sources[k]}</dd>
              </div>
            );
          })}
        </dl>
      )}
      {p?.notes.map((n) => <p key={n} className="lc-why">{n}</p>)}
      {p && <code className="mono lc-cli-line" data-testid="local-hf-argv" title="the command line it runs">{p.argv.join(" ")}</code>}
      <div className="lc-hf-go">
        <Button variant="primary" disabled={busy || !p || started} onClick={() => void startServe()} data-testid="local-hf-serve-go"
                title={p ? `${p.cli}${o.port ? ` --port ${o.port}` : ""}${o.keep ? " --keep" : ""}` : ""}>
          {busy ? "Starting…" : started ? "Started" : "Start"}
        </Button>
        {p && <span className="mono muted">then use it as {p.ref}</span>}
      </div>
      <Said k={`serve|${o.m.path}`} />
      <Cli text={p?.cli || ""} />
    </div>
  );
}

function DeleteCard() {
  const o = useHf((s) => (s.open?.act === "delete" ? s.open : null));
  const busy = useHf((s) => s.busy);
  const done = useHf((s) => (o ? s.said[`delete|${o.m.path}`]?.ok : false));
  if (!o) return null;
  const u = o.uses;
  const served = o.served.length > 0;
  const force = !!u?.any;
  return (
    <div className="lc-act-body" data-testid="local-hf-delete-card">
      <p className="mono">{o.m.path} · {gb(o.m.size)}</p>
      {!u ? <p className="mono muted">reading what names it…</p> : (
        <p className="lc-why" data-testid="local-hf-delete-uses">{u.line}</p>
      )}
      {served && <p className="lc-why" data-testid="local-hf-delete-served">{o.served[0].id} serves it on port {o.served[0].port}: stop it first</p>}
      <Button variant="danger" disabled={busy || !u || served || done} onClick={() => void deleteModel(o.m, force)} data-testid="local-hf-delete-go"
              title={served ? "a server Halo started serves it: Stop it first" : `${o.m.cli.rm}${force ? " --force" : ""}`}>
        {force ? "Delete anyway" : "Delete"}
      </Button>
      <Said k={`delete|${o.m.path}`} />
      <Cli text={`${o.m.cli.rm}${force ? " --force" : ""}`} />
    </div>
  );
}

function LogCard() {
  const o = useHf((s) => (s.open?.act === "log" ? s.open : null));
  if (!o) return null;
  return (
    <div className="lc-act-body" data-testid="local-hf-log-card">
      <p className="mono muted" title="the server's stdout and stderr">{o.path || "…"}</p>
      <pre className="mono lc-hf-log" data-testid="local-hf-log-lines">{o.lines ? o.lines.join("\n") || "(empty)" : "reading the log…"}</pre>
      <Button size="sm" onClick={() => void openLog(o.id)} data-testid="local-hf-log-again" title={`halo local log ${o.id}`}>Read again</Button>
      <Cli text={`halo local log ${o.id}`} />
    </div>
  );
}

function DownloadCard() {
  const o = useHf((s) => (s.open?.act === "download" ? s.open : null));
  const busy = useHf((s) => s.busy);
  if (!o) return null;
  const a = o.ask;
  return (
    <div className="lc-act-body" data-testid="local-dl-card">
      <p className="mono">{a.repo} {a.file}</p>
      {!a.licence ? <p className="mono muted">reading the repo's licence and files…</p> : (
        <p className="lc-why" data-testid="local-dl-licence" data-gated={a.licence.gated ? String(a.licence.gated) : ""}>{a.licence.line}</p>
      )}
      {a.licence?.prompt && <p className="muted" data-testid="local-dl-prompt">the repo says: {a.licence.prompt}</p>}
      {a.plan && (
        <ul className="lc-uses mono muted" data-testid="local-dl-files">
          {a.plan.files.map((f) => <li key={f.name} title="its size on the hub (?blobs=true)">{f.name} · {gb(f.size)}</li>)}
          <li>{a.plan.files.length} file(s), {gb(a.plan.total)} in all</li>
        </ul>
      )}
      <label className="mono muted">into{" "}
        <select value={a.dir} onChange={(e) => setDlDir(e.target.value)} data-testid="local-dl-dir" disabled={!a.dirs.length}>
          {a.dirs.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </label>
      {!a.dirs.length && <p className="lc-why">no huggingface.model_dirs folder yet: add one on Local -&gt; Hugging Face</p>}
      {a.needsToken && <p className="lc-why" data-testid="local-dl-token">the repo is gated: set HF_TOKEN (Setup -&gt; Providers -&gt; Hugging Face)</p>}
      <Button variant="primary" disabled={busy || !a.licence || a.needsToken || !a.dir} onClick={() => void acceptDownload()} data-testid="local-dl-go"
              title={a.cli || "halo local download"}>
        Accept and download
      </Button>
      <Said k={`dl|${a.repo}|${a.file}`} />
      <Cli text={a.cli} />
    </div>
  );
}

const TITLES: Record<string, string> = { serve: "Serve", delete: "Delete", log: "Log", download: "Download" };

export function HfCards() {
  const act = useHf((s) => s.open?.act || "");
  return (
    <Dialog open={!!act} onClose={close} title={TITLES[act] || ""} kicker="LOCAL · HUGGING FACE" className="lc-act-dialog" testid="local-hf-card">
      {act === "serve" && <ServeCard />}
      {act === "delete" && <DeleteCard />}
      {act === "log" && <LogCard />}
      {act === "download" && <DownloadCard />}
    </Dialog>
  );
}
