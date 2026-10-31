// Local -> Models' Adviser (3.3.7.0 R4, plans/local-model-fit-brief.md Part J; models_library/advise.py): the
// installed roster reviewed against the roles, the host's budget, the capability profiles and the host log, in four
// kinds -- gap, overlap, mismatch, freshness -- ranked by value per gigabyte. Each row says what it unlocks or frees
// and what it costs (the download, the VRAM, co-reside or pivot, the minutes), and has one button that names its one
// thing (Add = download then verify, Retire = the shelf's retire, Point = the role write); nothing runs until pressed.
// `halo local advise` prints the same lines.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { act, loadAdvice, useAdv, type Cost, type Suggestion } from "./advstore";

function costWords(c: Cost): string {
  const bits: string[] = [];
  if (c.download_gb) bits.push(`${c.download_gb} GB download (~${c.minutes} min)`);
  if (c.vram_gb) bits.push(`${c.vram_gb} GB VRAM` + (c.window ? ` at ${Math.round(c.window / 1024)}k` : ""));
  if (c.beside) bits.push(c.beside === "co-reside" ? "co-resides" : "a pivot");
  return bits.join(" · ") || "nothing to download";
}

function label(s: Suggestion): string {
  const a = s.action;
  if (a.verb === "add") return `Add ${a.model}`;
  if (a.verb === "retire") return `Retire ${a.model}`;
  if (a.verb === "point") return `Point ${a.role} at ${String(a.model || "").replace(/^ol:/, "")}`;
  return "";
}

function Row({ s }: { s: Suggestion }) {
  const busy = useAdv((st) => st.busy);
  const said = useAdv((st) => st.said[s.id]);
  const gain = s.unlocks ? `unlocks ${s.unlocks}` : s.frees ? `frees ${s.frees}` : "";
  return (
    <li className="lc-adv-row" data-testid="local-adviser-row" data-kind={s.kind} data-verb={s.action.verb} data-id={s.id}>
      <div className="lc-adv-head">
        <span className="og-chip mono" data-testid="local-adviser-kind">{s.kind}</span>
        <span className="lc-adv-says">{s.says}</span>
      </div>
      <div className="mono muted lc-adv-cost" data-testid="local-adviser-cost"
           title={`value ${s.value} · ${s.value_per_gb} per GB (the rank)`}>
        {[gain, costWords(s.cost)].filter(Boolean).join(" · ")}
      </div>
      <div className="lc-model-acts">
        {s.action.verb !== "none" && !said?.ok && (
          <Button size="sm" variant={s.rank === 1 ? "primary" : "ghost"} disabled={!!busy} onClick={() => void act(s)}
                  data-testid="local-adviser-act" title={`${s.action.what} (${s.action.cli})`}>
            {label(s)}
          </Button>
        )}
        <code className="mono lc-cli-line" data-testid="local-adviser-cli" title="the same from a terminal">{s.action.cli}</code>
      </div>
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-adviser-said">{said.text}</div>}
    </li>
  );
}

export function Adviser({ host }: { host?: string }) {
  const advice = useAdv((s) => s.advice);
  const error = useAdv((s) => s.error);
  useEffect(() => {
    void loadAdvice(host);
  }, [host]);
  const rows = advice?.suggestions;
  return (
    <details className="lc-block lc-adviser" data-testid="local-adviser" open={!!rows?.length}>
      <summary className="rail-label mono">ADVISER · {rows ? rows.length : "…"} SUGGESTION{rows?.length === 1 ? "" : "S"}</summary>
      {error && <p className="muted" data-testid="local-adviser-error">{error}</p>}
      {advice && <p className="mono muted" data-testid="local-adviser-head">{advice.head}</p>}
      {rows && !rows.length && <p className="muted">Nothing to add or retire: every role has a model, nothing overlaps.</p>}
      <ul className="lc-model-list">
        {(rows || []).map((s) => <Row key={s.id} s={s} />)}
      </ul>
      <Button size="sm" variant="ghost" onClick={() => void loadAdvice(host)} data-testid="local-adviser-again"
              title="halo local advise: review the roster again (no model, nothing runs)">Review again</Button>
    </details>
  );
}
