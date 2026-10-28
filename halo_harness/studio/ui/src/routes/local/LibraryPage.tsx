// Local -> Library (3.3.5.0 R2): what could be installed -- Ollama's library (its models at each size, their
// tags, sizes from the registry) and the Hugging Face Hub (GGUF and MLX repos, their files) -- every row with
// its card and a fit badge on the host picked at the window picked (LibraryRow.tsx), the controls on top
// (LibraryFilters.tsx), and one line naming where the list came from: live, or the shipped snapshot with its
// date and a Refresh. Every row is drawn (R0's WindowedRows keeps a long list quick). Nothing is pulled here:
// Pull lands in 3.3.5.0 R3; each row's pull line copies.
import { useEffect } from "react";
import { Button, Empty, WindowedRows } from "../../lib/ui";
import { LibraryFilters } from "./LibraryFilters";
import { LibraryRow } from "./LibraryRow";
import { loadLibrary, refreshLibrary, useLib } from "./libstore";

function when(at: number | null): string {
  if (!at) return "";
  const s = Math.max(0, Date.now() / 1000 - at);
  return s < 120 ? "just now" : s < 7200 ? `${Math.round(s / 60)} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`;
}

function SourceLine() {
  const data = useLib((s) => s.data);
  const loading = useLib((s) => s.loading);
  if (!data) return null;
  const o = data.sources.ollama;
  const h = data.sources.hf;
  const snap = !!o && o.startsWith("snapshot");
  return (
    <p className="mono muted lc-lib-source" data-testid="local-library-sources" data-ollama={o || ""} data-hf={h || ""}>
      {o && (
        <span title={data.notes.ollama || "ollama.com/library, cached a day"} data-testid={snap ? "local-library-snapshot" : undefined}>
          Ollama: {snap ? `snapshot from ${data.snapshot.taken}` : `live${data.cached_at ? `, read ${when(data.cached_at)}` : ""}`}
        </span>
      )}
      {h && <span title={data.notes.hf || "huggingface.co/api/models, cached an hour"}>Hugging Face: {h}</span>}
      <span>{data.total.toLocaleString("en-US")} rows{loading ? " · reading..." : ""}</span>
      <Button size="sm" onClick={() => void refreshLibrary()} disabled={loading} data-testid="local-library-refresh"
              title="read ollama.com and the hub again (the cache keeps the catalog a day, a search an hour)">
        {snap ? "Refresh" : "Read again"}
      </Button>
    </p>
  );
}

export function LibraryPage() {
  const data = useLib((s) => s.data);
  const error = useLib((s) => s.error);
  const intent = useLib((s) => s.filters.intent);
  useEffect(() => {
    void loadLibrary();
  }, []);
  const why = data?.intents.find((i) => i.id === intent)?.why || "";
  return (
    <div className="lc-models lc-library" data-testid="local-library">
      <LibraryFilters />
      <SourceLine />
      {why && <p className="muted lc-why" data-testid="local-library-intent-why">why this order: {why}</p>}
      {!data ? (
        error ? <Empty title="Studio could not read the library" body={error} /> : <div className="mono muted">reading the library...</div>
      ) : data.rows.length ? (
        <div role="list" className="lc-model-list" data-testid="local-library-list">
          <WindowedRows items={data.rows} render={(r) => <LibraryRow key={r.key} row={r} score={intent ? r.intent[intent] : undefined} />} />
        </div>
      ) : (
        <Empty title="Nothing in the library matches" body="Clear a filter, pick another source, or search for other words." testid="local-library-none" />
      )}
    </div>
  );
}
