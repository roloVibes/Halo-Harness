// One row of Local -> Library (3.3.5.0 R2): a model that could be installed -- its name and tag or file, the
// card's chips, its size on disk, the fit badge on the host picked at the window picked (idea 1; the numbers --
// weights + KV at that window against the card's free memory -- are its title, idea 2), downloads and updated,
// the licence and a gated mark; every number's title says where it came from. A click on the name unfolds the
// card's `how` lines (each "once pulled") and the model's other tags or files (GET local/library/<source>/<id>),
// each with its own fit. The action: Pull, disabled until 3.3.5.0 R3, and Copy for the pull line.
import { useState } from "react";
import { Button, FitMeter } from "../../lib/ui";
import { CardChips, CardDetail } from "../shared/ModelCard";
import { copyLine, count, detailKey, gb, loadDetail, useLib } from "./libstore";
import type { LibRow } from "./types";

function Copy({ line }: { line: string }) {
  const [said, setSaid] = useState("");
  const go = async () => setSaid((await copyLine(line)) ? "copied" : "by-hand");
  return (
    <span className="lc-lib-pull">
      <code className="mono lc-cli-line" data-testid="local-library-line">{line}</code>
      <Button size="sm" onClick={() => void go()} data-testid="local-library-copy" data-copied={said || undefined} title={`copy: ${line}`}>
        {said === "copied" ? "Copied" : said === "by-hand" ? "Copy it by hand" : "Copy"}
      </Button>
    </span>
  );
}

function Other({ r, on }: { r: LibRow; on: boolean }) {
  return (
    <li className="lc-lib-other" data-testid="local-library-other" data-name={r.name} data-fit={r.fit?.level || "unknown"} data-on={on || undefined}>
      <span className="mono">{r.tag_or_file || r.name}</span>
      <FitMeter fit={r.fit} />
      <span className="mono muted" title={r.sources?.size_bytes || "size on disk"}>{gb(r.size_bytes)}</span>
      {r.quant && <span className="mono muted" title={r.sources?.quant}>{r.quant}</span>}
      <Copy line={r.pull_line} />
    </li>
  );
}

function Unfolded({ row }: { row: LibRow }) {
  const id = row.source === "ollama" ? row.name : row.id; // an Ollama row asks for its own tag's manifest too
  const got = useLib((s) => s.details[detailKey(row.source, id)]);
  return (
    <div className="lc-lib-open" data-testid="local-library-open">
      <CardDetail card={row.card} refName={row.key} open />
      {row.fit?.why && <p className="mono muted lc-lib-why" data-testid="local-library-why">{row.fit.why}</p>}
      <div className="rail-label mono">{row.source === "ollama" ? "ITS TAGS" : "ITS FILES"}</div>
      {got === "loading" || got === undefined ? (
        <p className="mono muted">reading {row.source === "ollama" ? "the tags" : "the repo's files"}...</p>
      ) : typeof got === "string" ? (
        <p className="mono muted">{got}</p>
      ) : (
        <ul className="lc-lib-others" data-testid="local-library-others" data-note={got.note}>
          {got.rows.map((r) => <Other key={r.key} r={r} on={r.key === row.key} />)}
          {!got.rows.length && <li className="muted">{got.note || "nothing listed"}</li>}
        </ul>
      )}
    </div>
  );
}

export function LibraryRow({ row, score }: { row: LibRow; score?: number | null }) {
  const [open, setOpen] = useState(false);
  const toggle = () => {
    setOpen((o) => !o);
    if (!open) void loadDetail(row.source, row.source === "ollama" ? row.name : row.id);
  };
  const s = row.sources || {};
  return (
    <div role="listitem" className="lc-model lc-lib-row" data-testid="local-library-row" data-key={row.key} data-name={row.name} data-source={row.source}
        data-fit={row.fit?.level || "unknown"} data-score={score ?? undefined} data-purpose={row.card?.purpose || ""}>
      <div className="lc-model-top">
        <button type="button" className="lc-lib-name mono" onClick={toggle} aria-expanded={open} data-testid="local-library-unfold"
                title="its card, and its other tags or files with their fit">
          {open ? "▾" : "▸"} <b>{row.name}</b>
        </button>
        <span className="og-chip mono" data-testid="local-library-src" title={row.source === "ollama" ? "ollama.com/library" : "huggingface.co"}>
          {row.source === "ollama" ? "ollama" : row.kind === "mlx" ? "hf mlx" : "hf gguf"}
        </span>
        <CardChips card={row.card} />
        <span className="lc-lib-badge" data-testid="local-library-fit" data-level={row.fit?.level || "unknown"} title={row.fit?.why || ""}>
          <FitMeter fit={row.fit} />
        </span>
        <span className="spacer" />
        <span className="mono" data-testid="local-library-size" title={s.size_bytes || "size on disk"}>{gb(row.size_bytes)}{row.estimate ? " ≈" : ""}</span>
      </div>
      <div className="lc-model-mid mono muted">
        {row.params ? <span title={s.params}>{row.params}B</span> : null}
        {row.quant && <span title={s.quant}>{row.quant}</span>}
        {row.context ? <span title={s.context}>context {row.context.toLocaleString("en-US")}</span> : null}
        {row.downloads != null && <span title={s.downloads} data-testid="local-library-downloads">{count(row.downloads)} {row.source === "ollama" ? "pulls" : "downloads"}</span>}
        {row.updated && <span title="updated (the listing)">updated {row.updated}</span>}
        {row.license && <span title={s.license || "licence"}>licence {row.license}</span>}
        {row.gated ? <span className="lc-lib-gated" data-testid="local-library-gated" title="gated: the repo asks you to accept its terms; HF_TOKEN is sent for its files">gated</span> : null}
      </div>
      {row.description && <p className="muted lc-lib-desc">{row.description}</p>}
      <div className="lc-model-acts">
        <Button size="sm" variant="primary" disabled title="pulling lands in R3" data-testid="local-library-pull">Pull</Button>
        <Copy line={row.pull_line} />
      </div>
      {open && <Unfolded row={row} />}
    </div>
  );
}
