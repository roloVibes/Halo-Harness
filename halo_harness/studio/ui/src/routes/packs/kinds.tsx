// Three of a pack panel's kinds (3.2.0.0 R3), drawn by Studio's own
// components from the pack's data: `markdown` (a file of the pack, through
// lib/markdown: never HTML, never a remote image), `table` (a JSON list of
// rows from the pack's folder or its data folder; the columns the pack names,
// else the first row's keys) and `links` (a route into Studio, or an address
// that opens in a new tab).
import { useMemo } from "react";
import { Markdown } from "../../lib/markdown";
import { Empty } from "../../lib/ui";
import { openRoute, usePackFile } from "./nav";
import { packs } from "./store";
import type { PackPanel, Route } from "./types";

function Wait({ what }: { what: string }) {
  return <div className="og-wait mono muted">reading {what}...</div>;
}

function Failed({ error }: { error: string }) {
  return <Empty title="Studio could not read this panel's file" body={error} testid="pack-error" />;
}

export function PackMarkdown({ p }: { p: PackPanel }) {
  const f = usePackFile(p.file);
  if (f.loading) return <Wait what={p.source || "the file"} />;
  if (f.error) return <Failed error={f.error} />;
  return (
    <div className="pk-md" data-testid="pack-markdown">
      <Markdown text={f.text} />
    </div>
  );
}

type Rows = { rows: Record<string, unknown>[]; cols: string[]; error: string };

export function parseRows(text: string, columns?: string[]): Rows {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return { rows: [], cols: [], error: `not JSON: ${e instanceof Error ? e.message : String(e)}` };
  }
  const list = Array.isArray(data) ? data : Array.isArray((data as { rows?: unknown })?.rows) ? (data as { rows: unknown[] }).rows : null;
  if (!list) return { rows: [], cols: [], error: "not a list of rows: a JSON list, or {rows: [...]}" };
  const rows = list.filter((r): r is Record<string, unknown> => !!r && typeof r === "object" && !Array.isArray(r));
  const cols = columns && columns.length ? columns : Object.keys(rows[0] || {});
  return { rows, cols, error: "" };
}

const cell = (v: unknown) => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));

export function PackTable({ p }: { p: PackPanel }) {
  const f = usePackFile(p.file);
  const t = useMemo(() => parseRows(f.text, p.columns), [f.text, p.columns]);
  if (f.loading) return <Wait what={p.source || "the rows"} />;
  if (f.error) return <Failed error={f.error} />;
  if (t.error) return <Failed error={`${p.source}: ${t.error}`} />;
  if (!t.rows.length) return <Empty title="No rows yet" body={`${p.source} holds an empty list.`} testid="pack-table-empty" />;
  return (
    <div className="pk-table-wrap">
      <table className="pk-table" data-testid="pack-table">
        <thead>
          <tr>
            {t.cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {t.rows.map((r, i) => (
            <tr key={i} data-testid="pack-table-row">
              {t.cols.map((c) => (
                <td key={c} data-col={c}>
                  {cell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function routeText(r?: Route): string {
  if (!r) return "";
  const sec = packs.get().reg.packs.flatMap((x) => x.sections).find((s) => s.id === r.section);
  const panel = sec?.panels.find((x) => x.id === r.panel);
  return [sec ? sec.title : r.section, panel?.title].filter(Boolean).join(" / ");
}

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url;
  }
}

export function PackLinks({ p }: { p: PackPanel }) {
  const links = p.links || [];
  if (!links.length) return <Empty title="No links" body="This panel lists none." />;
  return (
    <ul className="pk-links" data-testid="pack-links">
      {links.map((l) => (
        <li key={l.label} className="pk-link-row">
          {l.url ? (
            <a className="og-link" href={l.url} target="_blank" rel="noopener noreferrer" data-testid="pack-link" data-url={l.url}>
              {l.label}
            </a>
          ) : (
            <button type="button" className="og-link" onClick={() => l.route && openRoute(l.route)} data-testid="pack-link" data-route={l.route?.section}>
              {l.label}
            </button>
          )}
          <span className="muted mono pk-link-where">{l.url ? hostOf(l.url) : `Studio: ${routeText(l.route)}`}</span>
        </li>
      ))}
    </ul>
  );
}
