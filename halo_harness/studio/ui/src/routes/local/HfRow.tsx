// One model on disk on Local -> Hugging Face (3.3.5.0 R5): its repo and file (or its path), the kind, the size, the
// card's chips, the fit meter on the host picked at the window picked (idea 1; the numbers are its title, idea 2),
// the other hosts' fit words, and which server Halo started serves it (its port). The actions: Serve (the card with
// the flags and their sources first), Stop and Log while one serves it, Use as default (`hf:local/<model>`, once
// served), Delete (the uses card). Every button's title is its `halo local` line; every number's, its source.
import { Button, FitMeter } from "../../lib/ui";
import { CardChips } from "../shared/ModelCard";
import { openDelete, openLog, openServe, stopServer, useHf } from "./hfstore";
import { gb } from "./libstore";
import { useAsDefault, useLocal } from "./store";
import type { HfModel } from "./types";

function Said({ k }: { k: string }) {
  const s = useHf((st) => st.said[k]);
  return s ? <span className="mono lc-said" data-ok={s.ok || undefined} data-testid="local-hf-row-said">{s.text}</span> : null;
}

export function HfRow({ m }: { m: HfModel }) {
  const busy = useHf((s) => s.busy);
  const localBusy = useLocal((s) => !!s.busy);
  const def = useLocal((s) => (m.ref ? s.said[`default|${m.ref}`] : undefined));
  const on = m.served.filter((s) => s.alive);
  const srv = on[0];
  const name = m.repo ? m.repo : m.path;
  return (
    <li className="lc-model lc-hf-row" data-testid="local-hf-row" data-path={m.path} data-kind={m.kind} data-model={m.model}
        data-fit={m.fit?.level || "unknown"} data-served={srv ? srv.port : undefined}>
      <div className="lc-model-top">
        <b className="mono" title={m.path}>{name}</b>
        {m.file && <span className="mono">{m.file}</span>}
        <span className="og-chip mono" data-testid="local-hf-kind" title={m.hub ? "the hub cache's layout (models--<org>--<name>)" : "a file in the folder"}>{m.kind}</span>
        <CardChips card={m.card} />
        <span data-testid="local-hf-fit" data-level={m.fit?.level || "unknown"}><FitMeter fit={m.fit} /></span>
        <span className="spacer" />
        <span className="mono" data-testid="local-hf-size" title={m.sources.size_bytes || "on disk"}>{gb(m.size)}</span>
      </div>
      <div className="lc-model-mid mono muted">
        {m.quant && <span title={m.sources.quant}>{m.quant}</span>}
        {m.context ? <span title={m.sources.context}>context {m.context.toLocaleString("en-US")}</span> : null}
        {Object.entries(m.fits).map(([h, f]) => (
          <span key={h} data-testid="local-hf-fit-host" data-host={h} data-level={f.level} title={f.why}>{h}: {f.level}</span>
        ))}
        {srv && (
          <span className="og-chip mono lc-installed-chip" data-testid="local-hf-served" title={`${srv.kind} ${srv.id}, ${srv.url}`}>
            served by {srv.id} on :{srv.port}{srv.ready ? "" : " (loading)"}
          </span>
        )}
      </div>
      <div className="lc-model-acts">
        {!srv && (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void openServe(m)} data-testid="local-hf-serve" title={m.cli.serve}>Serve</Button>
        )}
        {srv && (
          <>
            <Button size="sm" disabled={busy} onClick={() => void stopServer(srv.id, `row|${m.path}`)} data-testid="local-hf-stop"
                    title={`halo local stop ${srv.id} (terminate, then kill after 10 s)`}>Stop</Button>
            <Button size="sm" onClick={() => void openLog(srv.id)} data-testid="local-hf-log" title={`halo local log ${srv.id}`}>Log</Button>
          </>
        )}
        {m.ref && (
          <Button size="sm" disabled={localBusy} onClick={() => void useAsDefault(m.ref || "")} data-testid="local-hf-default"
                  title={`model = ${m.ref} (Setup's save)`}>Use as default</Button>
        )}
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={() => void openDelete(m)} data-testid="local-hf-delete" title={m.cli.rm}>Delete</Button>
        <Said k={`row|${m.path}`} />
        <Said k={`delete|${m.path}`} />
        {def && <span className="mono lc-said" data-ok={def.ok || undefined} data-testid="local-hf-default-said">{def.text}</span>}
      </div>
    </li>
  );
}
