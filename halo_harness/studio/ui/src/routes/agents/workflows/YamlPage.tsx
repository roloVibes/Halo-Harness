// The inspector's YAML page (3.3.16.0 R3): the square's file as it is on disk, read through GET workflows/yaml, with
// where it lives. Edits go through the Budget and Limits pages (a square of yours) or `halo workflows new` (a copy).
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { Button } from "../../../lib/ui";
import { setPage, type Square } from "./store";

export function YamlPage({ q }: { q: Square }) {
  const [got, setGot] = useState<{ text: string; path: string; writable: boolean } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    api.get<{ text: string; path: string; writable: boolean }>("workflows/yaml", { ref: q.ref })
      .then((g) => live && setGot(g))
      .catch((e) => live && setErr((e as Error).message || "could not read the file"));
    return () => void (live = false);
  }, [q.ref]);
  return (
    <div className="wf-page" data-testid="wf-page-yaml">
      <div className="wf-page-head" data-density="bar">
        <Button size="sm" variant="ghost" onClick={() => setPage("summary")} data-testid="wf-page-back">Back</Button>
        <b className="mono">{q.ref}</b><span className="muted">YAML</span>
      </div>
      <p className="muted mono wf-path" title={got?.path || q.path}>{got?.path || q.path}</p>
      {err ? <p className="wf-err">{err}</p> : <pre className="wf-yaml mono" data-testid="wf-yaml">{got ? got.text : "reading ..."}</pre>}
    </div>
  );
}
