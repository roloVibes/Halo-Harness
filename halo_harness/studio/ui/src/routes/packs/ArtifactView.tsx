// A typed artifact, drawn by its schema's view hint (3.2.0.0 R5,
// halo_harness/packs/typed.py `x-halo-view`): `table` (one row per item of the
// document's first list of objects -- or of the document when it is a list --
// with its other keys above the table), `markdown` (the document's
// `markdown`, `text` or first text value, through lib/markdown: never HTML) and
// `keyvalue` (the default: each key and its value). PackArtifact is a pack
// panel of kind `artifact` (its `latest` source is the newest run's artifact
// of the schema, GET pack/<id>/artifact/<schema>); Orchestra's run view uses
// ArtifactView for a run's own artifacts (orchestra/Artifacts.tsx).
import { useMemo } from "react";
import { Markdown } from "../../lib/markdown";
import { Empty } from "../../lib/ui";
import { usePackFile } from "./nav";
import type { PackPanel } from "./types";

export type ArtifactPayload = {
  name: string;
  schema: string;
  view: "table" | "markdown" | "keyvalue";
  columns: string[];
  data: unknown;
  run: string;
  path: string;
  ok: boolean;
  problems: string[];
  state?: string;
  workflow?: string;
  why?: string;
};

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => !!v && typeof v === "object" && !Array.isArray(v);
const cell = (v: unknown) => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));

function split(doc: unknown): { rows: Obj[]; rest: [string, unknown][] } {
  if (Array.isArray(doc)) return { rows: doc.filter(isObj), rest: [] };
  if (!isObj(doc)) return { rows: [], rest: [] };
  const key = Object.keys(doc).find((k) => Array.isArray(doc[k]) && (doc[k] as unknown[]).some(isObj));
  return { rows: key ? (doc[key] as unknown[]).filter(isObj) : [], rest: Object.entries(doc).filter(([k]) => k !== key) };
}

function KeyValue({ entries }: { entries: [string, unknown][] }) {
  return (
    <dl className="pk-art-kv mono" data-testid="artifact-kv">
      {entries.map(([k, v]) => (
        <div key={k} className="pk-art-kv-row" data-key={k}>
          <dt>{k}</dt>
          <dd>{cell(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function textOf(doc: unknown): string {
  if (typeof doc === "string") return doc;
  if (!isObj(doc)) return "";
  const named = ["markdown", "text", "body"].find((k) => typeof doc[k] === "string");
  const first = named || Object.keys(doc).find((k) => typeof doc[k] === "string");
  return first ? String(doc[first]) : "";
}

export function ArtifactView({ doc, view, columns }: { doc: unknown; view: string; columns?: string[] }) {
  const t = useMemo(() => split(doc), [doc]);
  if (doc === null || doc === undefined) return <Empty title="No document" body="The artifact holds nothing." testid="artifact-empty" />;
  if (view === "markdown")
    return (
      <div className="pk-md" data-testid="artifact-md">
        <Markdown text={textOf(doc)} />
      </div>
    );
  if (view !== "table" || !t.rows.length) return <KeyValue entries={isObj(doc) ? Object.entries(doc) : [["value", doc]]} />;
  const cols = columns && columns.length ? columns : Object.keys(t.rows[0]);
  return (
    <div className="pk-art" data-testid="artifact-table-view">
      {t.rest.length > 0 && <KeyValue entries={t.rest} />}
      <div className="pk-table-wrap">
        <table className="pk-table" data-testid="artifact-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {t.rows.map((r, i) => (
              <tr key={i} data-testid="artifact-row">
                {cols.map((c) => (
                  <td key={c} data-col={c}>
                    {cell(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ArtifactProblems({ list }: { list: string[] }) {
  if (!list.length) return null;
  return (
    <ul className="pk-art-problems" data-testid="artifact-problems">
      {list.map((p) => (
        <li key={p} className="field-error">
          {p}
        </li>
      ))}
    </ul>
  );
}

function parse(text: string, p: PackPanel): ArtifactPayload | string {
  try {
    const got = JSON.parse(text) as unknown;
    if (p.source === "latest" || !p.source) return got as ArtifactPayload;
    return { name: p.name, schema: p.schema || "", view: (p.view || "keyvalue") as ArtifactPayload["view"], columns: [], data: got,
             run: "", path: p.source, ok: true, problems: [] };
  } catch (e) {
    return `not JSON: ${e instanceof Error ? e.message : String(e)}`;
  }
}

export function PackArtifact({ p }: { p: PackPanel }) {
  const f = usePackFile(p.file);
  const a = useMemo(() => (f.text ? parse(f.text, p) : null), [f.text, p]);
  if (f.loading) return <div className="og-wait mono muted">reading the {p.schema} artifact...</div>;
  if (f.error) return <Empty title="Studio could not read this artifact" body={f.error} testid="pack-error" />;
  if (typeof a === "string") return <Empty title="This artifact is not JSON" body={a} testid="pack-error" />;
  if (!a || a.data === null || a.data === undefined)
    return <Empty title={`No ${p.schema} yet`} body={a?.why || "A run of the pack's workflow writes one."} testid="artifact-empty" />;
  return (
    <div className="pk-art-panel" data-testid="pack-artifact" data-view={a.view} data-run={a.run}>
      <div className="pk-art-meta mono muted" data-testid="artifact-meta">
        {a.schema} · {a.view}
        {a.run ? ` · run ${a.run}` : ""}
        {a.workflow ? ` · ${a.workflow}` : ""}
      </div>
      <ArtifactProblems list={a.problems || []} />
      <ArtifactView doc={a.data} view={a.view} columns={a.columns} />
    </div>
  );
}
