// One Settings page (3.3.3.0 R2): the open group's rows, under a head that
// says which group it is and what its keys decide (routes/help-settings.ts),
// its help lines one click away (closed by default), and the search box. With
// words in the search the page lists the hits across every group instead, a
// caption per group. A palette entry lands here with its row lit for a moment
// and scrolled into view.
import { useEffect, useMemo, useRef } from "react";
import { Empty } from "../../lib/ui";
import { HELP } from "../help";
import { hits, setQuery, usePages } from "./pages";
import { SettingRow } from "./Row";
import { useSettings, type Row } from "./store";

function Head({ title, about, help, count }: { title: string; about: string; help: string; count: string }) {
  const query = usePages((s) => s.query);
  const lines = help.split("\n").filter(Boolean);
  return (
    <header className="st-page-head">
      <div className="st-page-top">
        <div className="st-page-kicker mono">SETTINGS · {count}</div>
        <input type="search" className="st-search mono" value={query} placeholder="Search every key: fleet port, theme, ollama ..." aria-label="Search every key"
               data-testid="settings-search" onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setQuery("")} />
      </div>
      <h2 className="st-page-title" data-testid="settings-page-title">
        {title}
      </h2>
      {about && <p className="st-lead muted">{about}</p>}
      {lines.length > 0 && (
        <details className="st-page-help" data-testid="settings-page-help">
          <summary className="mono">How this page works</summary>
          <ul>
            {lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </header>
  );
}

function Hits({ query }: { query: string }) {
  const rows = useSettings((s) => s.rows);
  const groups = useSettings((s) => s.groups);
  const found = useMemo(() => {
    const out: { id: string; title: string; rows: Row[] }[] = [];
    for (const g of groups) {
      const rs = rows.filter((r) => r.group === g.id && hits(r, query, g.title));
      if (rs.length) out.push({ id: g.id, title: g.title, rows: rs });
    }
    return out;
  }, [rows, groups, query]);
  if (!found.length) return <Empty title="No key matches" body="Try a word of its title, its key or its help line." testid="settings-no-hits" />;
  return (
    <div className="st-hits" data-testid="settings-hits">
      {found.map((g) => (
        <section key={g.id} className="st-hits-group" data-testid="settings-hits-group" data-group={g.id} aria-label={g.title}>
          <h3 className="st-hits-caption mono">{g.title}</h3>
          {g.rows.map((r) => (
            <SettingRow key={r.key} row={r} />
          ))}
        </section>
      ))}
    </div>
  );
}

export function SettingsPage() {
  const page = usePages((s) => s.page);
  const query = usePages((s) => s.query.trim());
  const lit = usePages((s) => s.lit);
  const rows = useSettings((s) => s.rows);
  const groups = useSettings((s) => s.groups);
  const ready = useSettings((s) => s.loaded && s.rows.length > 0);
  const error = useSettings((s) => s.error);
  const ref = useRef<HTMLElement>(null);
  const group = groups.find((g) => g.id === page) || groups[0];
  const own = useMemo(() => rows.filter((r) => r.group === group?.id), [rows, group?.id]);
  useEffect(() => {
    if (!lit || !ref.current) return;
    const el = ref.current.querySelector<HTMLElement>(`[data-testid=settings-row][data-key="${CSS.escape(lit)}"]`);
    el?.scrollIntoView({ block: "center" });
  }, [lit, ready, page]);
  useEffect(() => {
    void ref.current?.closest(".st-scroll")?.scrollTo({ top: 0 }); // braces: a scrollTo that answers a promise is no cleanup
  }, [page]);
  if (!ready)
    return (
      <section className="st-page-card" data-testid="settings-group-page">
        {error ? <p className="st-error">Studio could not read the settings: {error}</p> : <div className="mono muted">reading the settings...</div>}
      </section>
    );
  const h = HELP[`settings-${group.id}`] || { about: "", help: "" };
  const count = query ? "SEARCH" : `${own.length} KEY${own.length === 1 ? "" : "S"}`;
  return (
    <section className="st-page-card" ref={ref} data-testid="settings-group-page" data-group={query ? "" : group.id} aria-label={`Settings: ${group.title}`}>
      <Head title={query ? `Every key matching "${query}"` : group.title} about={query ? "" : h.about} help={query ? "" : h.help} count={count} />
      {query ? (
        <Hits query={query} />
      ) : (
        <div className="st-rows">
          {own.map((r) => (
            <SettingRow key={r.key} row={r} />
          ))}
        </div>
      )}
    </section>
  );
}
