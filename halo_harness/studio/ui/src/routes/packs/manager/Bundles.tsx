// The Pack Manager's Bundles group (3.3.7.0 R5, plans/local-model-fit-brief.md Part L): every bundle here and shipped,
// each a tick with one line under it -- the honest verdict, computed before anything downloads: ready ("fits today --
// 1.2 GB reserved leaves ~20.8 GB, the coder (18.9 GB) still fits beside it, barely"), needs N downloads (each tag,
// its size and fit, and the one button that starts Download and verify), or won't work with the ways out, each a
// number. The tick turns a ready bundle on (its reservation claimed, held by this Studio) and off. `halo pack verdict
// <id>` and `halo pack on|off <id>` are the same from a terminal.
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { download, startBundles, tick, useBundles, type BundleRow } from "./bundlestore";

const STATE: Record<string, string> = { ready: "ready", downloads: "needs downloads", wont: "won't work", unknown: "not judged" };

function Row({ b }: { b: BundleRow }) {
  const busy = useBundles((s) => s.busy);
  const said = useBundles((s) => s.said[b.id]);
  const v = b.verdict;
  const can = b.on || v?.state === "ready";
  return (
    <li className="pm-bundle" data-testid="pm-bundle-row" data-id={b.id} data-state={v?.state || "unknown"} data-on={b.on || undefined}>
      <div className="pm-bundle-head">
        <label className="og-switch mono" title={b.on ? b.cli.off : can ? b.cli.on : "only a ready bundle turns on"}>
          <input type="checkbox" checked={b.on} disabled={!!busy || !can} onChange={() => void tick(b)} data-testid="pm-bundle-tick" />
          {b.name}
        </label>
        <span className="og-chip mono" data-testid="pm-bundle-state">{STATE[v?.state || "unknown"]}</span>
        <span className="muted pm-bundle-desc">{b.description}</span>
      </div>
      {v && <div className="mono pm-bundle-says" data-testid="pm-bundle-says">{v.says}</div>}
      {v && v.options.length > 0 && (
        <ul className="pm-bundle-options mono muted" data-testid="pm-bundle-options">
          {v.options.map((o) => (
            <li key={o.says} data-kind={o.kind}>{o.kind === "warn" ? "! " : "- "}{o.says}</li>
          ))}
        </ul>
      )}
      <div className="pm-bundle-acts">
        {v?.button && !said?.ok && (
          <Button size="sm" variant="primary" disabled={!!busy} onClick={() => void download(b)} data-testid="pm-bundle-download"
                  title={`Download and verify: ${v.button.tags.join(", ")} onto ${v.button.host}`}>
            {v.button.label}
          </Button>
        )}
        <code className="mono lc-cli-line" title="the same from a terminal">{b.on ? b.cli.off : b.cli.verdict}</code>
      </div>
      {said && <pre className="pm-lines mono" data-ok={said.ok || undefined} data-testid="pm-bundle-said">{said.lines.join("\n")}</pre>}
      {b.on && v?.claims_line && <div className="mono muted" data-testid="pm-bundle-claims">{v.claims_line}</div>}
    </li>
  );
}

export function BundlesGroup() {
  const rows = useBundles((s) => s.rows);
  const error = useBundles((s) => s.error);
  useEffect(() => {
    startBundles();
  }, []);
  return (
    <section className="pm-bundles" aria-label="Bundles" data-testid="pm-bundles">
      <div className="rail-label mono">BUNDLES · A PACK WITH A RESOURCE CLAIM</div>
      {error && <p className="muted" data-testid="pm-bundles-error">{error}</p>}
      {!rows && !error && <div className="og-wait mono muted">judging the bundles...</div>}
      <ul className="pm-bundle-list">
        {(rows || []).map((b) => <Row key={b.id} b={b} />)}
      </ul>
    </section>
  );
}
