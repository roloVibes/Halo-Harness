// The card a Models row's actions menu opens (3.3.5.0 R3; routes/local/ctl.ts): Show (the /api/show facts beside the
// model card), Make a tuned twin (the window picked, the twin's name and what it costs: a manifest, no new blobs),
// Copy / Rename (the new name), Delete (the uses card first; "Delete anyway" when something uses it and no session is
// on it). Each card ends with the `halo models` line that does the same and the answer of the last action.
import { useEffect, useState } from "react";
import { Button, Dialog } from "../../lib/ui";
import { CardDetail } from "../shared/ModelCard";
import { closeAct, copyModel, deleteModel, line, makeTwin, planTwin, useCtl } from "./ctl";
import { WINDOWS } from "./libstore";
import { RetireCard } from "./ShelfBits";
import type { ModelEntry } from "./types";

const TITLES = { show: "Show", twin: "Make a tuned twin", copy: "Copy", rename: "Rename", delete: "Delete", retire: "Retire" };

function Said() {
  const s = useCtl((c) => c.said);
  return s ? <p className="mono lc-said" data-ok={s.ok || undefined} data-testid="local-act-said">{s.text}</p> : null;
}

function Cli({ text }: { text: string }) {
  return <code className="mono lc-cli-line" data-testid="local-act-cli" title="the same from a terminal">{text}</code>;
}

function ShowCard({ host, m }: { host: string; m: ModelEntry }) {
  const got = useCtl((c) => c.show);
  const f = got?.facts;
  const s = got?.show || {};
  return (
    <div className="lc-show" data-testid="local-show-card">
      <div className="lc-show-facts" data-testid="local-show-facts">
        <div className="rail-label mono">/API/SHOW</div>
        {!got ? <p className="mono muted">reading /api/show…</p> : (
          <dl className="lc-facts">
            {f && Object.entries(f).filter(([, v]) => v != null && v !== "").map(([k, v]) => (
              <div key={k} data-fact={k} title={`/api/show ${k === "context" ? "model_info <family>.context_length" : "details"}`}>
                <dt className="muted">{k}</dt><dd className="mono">{typeof v === "number" ? v.toLocaleString("en-US") : String(v)}</dd>
              </div>
            ))}
            {s.capabilities?.length ? <div data-fact="capabilities" title="/api/show capabilities"><dt className="muted">capabilities</dt><dd className="mono">{s.capabilities.join(", ")}</dd></div> : null}
            {s.params && Object.keys(s.params).length ? (
              <div data-fact="parameters" title="/api/show parameters (the Modelfile's PARAMETER lines)">
                <dt className="muted">parameters</dt><dd className="mono">{Object.entries(s.params).map(([k, v]) => `${k} ${v}`).join(" · ")}</dd>
              </div>
            ) : null}
            {s.license ? <div data-fact="license" title="/api/show license"><dt className="muted">licence</dt><dd className="mono">{String(s.license).split("\n")[0].slice(0, 120)}</dd></div> : null}
            {s.template ? <div data-fact="template" title={String(s.template).slice(0, 600)}><dt className="muted">template</dt><dd className="mono">{String(s.template).length.toLocaleString("en-US")} characters</dd></div> : null}
          </dl>
        )}
      </div>
      <div className="lc-show-card">
        <div className="rail-label mono">THE MODEL CARD</div>
        <CardDetail card={m.card} refName={m.ref} open />
      </div>
      <Cli text={got?.cli || line("show", host, m.model)} />
    </div>
  );
}

function TwinCard({ host, m }: { host: string; m: ModelEntry }) {
  const plan = useCtl((c) => c.plan);
  const busy = useCtl((c) => c.busy);
  const [win, setWin] = useState(m.profile?.num_ctx || m.card?.window?.tokens || 32768);
  useEffect(() => {
    void planTwin(host, m.model, win);
  }, [host, m.model, win]);
  return (
    <div className="lc-act-body" data-testid="local-twin">
      <label className="mono muted">window{" "}
        <select value={win} onChange={(e) => setWin(Number(e.target.value))} data-testid="local-twin-window">
          {Array.from(new Set([win, ...WINDOWS])).sort((a, b) => a - b).map((w) => <option key={w} value={w}>{w.toLocaleString("en-US")}</option>)}
        </select>
      </label>
      {plan ? (
        <>
          <p className="mono">the twin: <b data-testid="local-twin-name">{plan.twin}</b></p>
          <p className="muted lc-why" title="ollama_tune's Modelfile through /api/create">{plan.line}</p>
          <p className="lc-why" data-testid="local-twin-cost" title="what it costs">costs {plan.cost}</p>
        </>
      ) : <p className="mono muted">planning the twin…</p>}
      <Button size="sm" variant="primary" disabled={busy || !plan} onClick={() => void makeTwin(host, m.model, win)} data-testid="local-twin-make"
              title={plan?.cli || line("twin", host, m.model, "--window", String(win))}>Make it</Button>
      <Cli text={plan?.cli || line("twin", host, m.model, "--window", String(win))} />
    </div>
  );
}

function CopyCard({ host, m, rename }: { host: string; m: ModelEntry; rename: boolean }) {
  const busy = useCtl((c) => c.busy);
  const [base, tag] = m.model.includes(":") ? [m.model.slice(0, m.model.lastIndexOf(":")), m.model.slice(m.model.lastIndexOf(":") + 1)] : [m.model, "latest"];
  const [dst, setDst] = useState(`${base}-${rename ? "new" : "copy"}:${tag}`);
  const cli = line(rename ? "rename" : "copy", host, m.model, dst.trim());
  return (
    <div className="lc-act-body" data-testid="local-copy" data-mode={rename ? "rename" : "copy"}>
      <p className="muted lc-why">{rename ? "A copy under the new name, then the old name deleted (Ollama has no rename)." : "A second name for the same layers: no download, a manifest on disk."}</p>
      <input className="input mono" value={dst} onChange={(e) => setDst(e.target.value)} aria-label="the new name" data-testid="local-copy-name" />
      <Button size="sm" variant="primary" disabled={busy || !dst.trim() || dst.trim() === m.model} onClick={() => void copyModel(host, m.model, dst.trim(), rename)}
              data-testid="local-copy-go" title={cli}>{rename ? "Rename" : "Copy"}</Button>
      <Cli text={cli} />
    </div>
  );
}

function DeleteCard({ host, m }: { host: string; m: ModelEntry }) {
  const u = useCtl((c) => c.uses);
  const busy = useCtl((c) => c.busy);
  const said = useCtl((c) => c.said);
  const gone = !!said?.ok;
  if (!u) return <p className="mono muted">reading what uses it…</p>;
  const force = u.any;
  const cli = line("rm", host, m.model) + (force ? " --force" : "");
  return (
    <div className="lc-act-body" data-testid="local-delete" data-any={u.any || undefined} data-live={u.live}>
      <p className="lc-why" data-testid="local-delete-uses">{u.line}</p>
      {u.any && (
        <ul className="lc-uses mono muted">
          {u.lineups.map((x) => <li key={`l${x.name}${x.role}`} data-use="lineup">the {x.role} in {x.name}</li>)}
          {u.roles.map((r) => <li key={`r${r}`} data-use="role">the {r} role (config.json roles)</li>)}
          {u.default_model && <li data-use="model">the default model (model)</li>}
          {u.compaction && <li data-use="compaction">the compaction model (compactionModel)</li>}
          {u.profiles.map((p) => <li key={`p${p}`} data-use="profile">the steward profile {p} (ollama.profiles)</li>)}
          {u.sessions.map((s) => <li key={`s${s.id}`} data-use="session">live session {s.title || s.id}</li>)}
        </ul>
      )}
      {!gone && (
        <Button size="sm" variant="primary" disabled={busy || u.live > 0} onClick={() => void deleteModel(host, m.model, force)} data-testid="local-delete-go"
                data-force={force || undefined} title={u.live > 0 ? "a live session is on it: it can go once that session ends or moves to another model" : cli}>
          {force ? "Delete anyway" : "Delete"}
        </Button>
      )}
      <Cli text={cli} />
    </div>
  );
}

export function ModelActCard() {
  const open = useCtl((c) => c.open);
  if (!open) return null;
  const { act, host, m } = open;
  return (
    <Dialog open onClose={closeAct} title={`${TITLES[act]}: ${m.model}`} kicker={`on ${host}`} testid="local-act-card" className="lc-act-dialog">
      {act === "show" && <ShowCard host={host} m={m} />}
      {act === "twin" && <TwinCard host={host} m={m} />}
      {(act === "copy" || act === "rename") && <CopyCard host={host} m={m} rename={act === "rename"} />}
      {act === "delete" && <DeleteCard host={host} m={m} />}
      {act === "retire" && <RetireCard host={host} m={m} />}
      <Said />
    </Dialog>
  );
}
