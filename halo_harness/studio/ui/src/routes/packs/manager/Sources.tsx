// pm-sources (3.2.0.0 R6): where `halo pack install <id>` looks, in order --
// the folders and git urls of packs.sources (Add, Remove), then the packs
// Halo ships -- and the packs each holds. A pack not installed here has
// Install (into ~/.halo/packs/, or this repo's .halo/packs/ with "into this
// repo"); a click on its name shows it in Details. A git url is cloned only
// when you install it, so its pack shows by name alone. No marketplace: only
// what your config names and what Halo ships.
import { useState } from "react";
import { Button, Empty } from "../../../lib/ui";
import { addSource, cli, installPack, removeSource, selectPack, useMgr } from "./store";
import type { Source, SourcePack } from "./types";

const KIND: Record<Source["kind"], string> = { folder: "folder", url: "git url", shipped: "shipped with Halo" };

function PackLine({ p, project }: { p: SourcePack; project: boolean }) {
  const busy = useMgr((s) => !!s.busy);
  const on = useMgr((s) => s.sel === p.id);
  return (
    <li className="pm-src-pack" data-testid="pm-source-pack" data-id={p.id} data-installed={p.installed || undefined}>
      <button className="og-link pm-src-name" aria-pressed={on} onClick={() => selectPack(p.id)} title="Show it in Details" disabled={!p.details && !p.installed}>
        {p.name || p.id}
      </button>
      <span className="mono muted">{p.id} {p.version}</span>
      {p.installed ? (
        <span className="og-chip mono" data-testid="pm-source-installed">installed</span>
      ) : (
        <Button size="sm" variant="primary" disabled={busy || p.problems.length > 0} onClick={() => void installPack(p.path, project, p.id)}
                title={p.problems[0] || cli.install(p.id, project)} data-testid="pm-install">
          Install
        </Button>
      )}
      <span className="pm-src-desc muted">{p.problems[0] || p.description}</span>
    </li>
  );
}

function SourceBox({ s, project }: { s: Source; project: boolean }) {
  const busy = useMgr((st) => !!st.busy);
  return (
    <section className="pm-src" data-testid="pm-source" data-kind={s.kind}>
      <header className="pm-src-head">
        <span className="og-chip mono">{KIND[s.kind]}</span>
        <span className="pm-src-where mono" title={s.source}>{s.source}</span>
        {s.configured && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void removeSource(s.source)} title={`halo pack sources remove ${s.source}`} data-testid="pm-source-remove">
            Remove
          </Button>
        )}
      </header>
      {s.problem && <p className="pm-row-warn">{s.problem}</p>}
      {s.packs.length ? (
        <ul className="pm-src-packs">
          {s.packs.map((p) => (
            <PackLine key={p.id + p.path} p={p} project={project} />
          ))}
        </ul>
      ) : (
        !s.problem && <p className="muted">No pack in this folder yet.</p>
      )}
    </section>
  );
}

export function SourcesDetail() {
  const data = useMgr((s) => s.data);
  const busy = useMgr((s) => !!s.busy);
  const [text, setText] = useState("");
  const [project, setProject] = useState(false);
  if (!data) return <div className="og-wait mono muted">reading the sources...</div>;
  const add = async () => {
    if (await addSource(text.trim())) setText("");
  };
  return (
    <div className="pm-sources" data-testid="pm-sources-body">
      <form className="pm-src-add" onSubmit={(e) => (e.preventDefault(), void add())}>
        <input className="input mono" value={text} onChange={(e) => setText(e.target.value)} placeholder="a folder of packs, a pack's folder or a git url"
               aria-label="A source to add to packs.sources" data-testid="pm-source-add-input" />
        <Button type="submit" size="sm" disabled={busy || !text.trim()} title="halo pack sources add <folder|git url>" data-testid="pm-source-add">Add source</Button>
        <label className="og-switch mono" title="Install into this repo's .halo/packs/ (halo pack install --project)">
          <input type="checkbox" checked={project} onChange={(e) => setProject(e.target.checked)} data-testid="pm-project" />
          into this repo
        </label>
      </form>
      {data.sources.length ? data.sources.map((s) => <SourceBox key={s.source} s={s} project={project} />) : <Empty title="No sources" />}
    </div>
  );
}

export function SourcesGlance() {
  const free = useMgr((s) => (s.data?.sources || []).reduce((n, src) => n + src.packs.filter((p) => !p.installed).length, 0));
  return (
    <div className="glance">
      <div className="glance-kicker mono">SOURCES</div>
      <div className="glance-text mono">{free} to install</div>
      <div className="glance-hint">packs.sources, then the packs Halo ships</div>
    </div>
  );
}
