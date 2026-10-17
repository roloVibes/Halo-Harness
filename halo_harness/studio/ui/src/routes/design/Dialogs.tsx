// The Design dialogs (3.0.7.0 R3, one at a time: store `dialog`): New
// project, Rename an artboard, Delete one (asks first), Export (what and
// which artboard) and what it wrote, the Handoff bundle's path and the
// command that continues from it, and an artboard's contrast table; R3b:
// what a design-system Sync found.
import { useState } from "react";
import { Button, Dialog } from "../../lib/ui";
import { toast } from "../../lib/store";
import { exportAs, newProject, remove, rename } from "./actions";
import { artboard, closeDialog, useDesign } from "./store";
import { EXPORTS, type DesignDialog } from "./types";

function NewProject() {
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const busy = useDesign((s) => s.busy === "new");
  const go = () => void newProject(name, model.trim());
  return (
    <Dialog open onClose={closeDialog} title="New design project" kicker="DESIGN · PROJECT" testid="design-new-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!name.trim() || busy} onClick={go} data-testid="design-new-go">Create project</Button></>}>
      <label className="fd-field">
        <span className="rail-label mono">NAME</span>
        <input className="input" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} placeholder="Launch page" data-testid="design-new-name" />
      </label>
      <label className="fd-field">
        <span className="rail-label mono">MODEL (OPTIONAL)</span>
        <input className="input mono" value={model} onChange={(e) => setModel(e.target.value)} placeholder="the default model" />
      </label>
      <p className="muted">A folder under ~/.halo/design/; every turn in it saves a version of the artboards it changed.</p>
    </Dialog>
  );
}

function Rename({ aid }: { aid: string }) {
  const a = useDesign((s) => artboard(s, aid));
  const [name, setName] = useState(a?.title || aid);
  const go = () => name.trim() && void rename(aid, name.trim());
  return (
    <Dialog open onClose={closeDialog} title={`Rename ${a?.title || aid}`} kicker="DESIGN · ARTBOARD" testid="design-rename-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!name.trim()} onClick={go} data-testid="design-rename-go">Rename</Button></>}>
      <input className="input" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} aria-label="New name" data-testid="design-rename-name" />
      <p className="muted">The title changes; the artboard's id ({aid}), its files and its versions stay.</p>
    </Dialog>
  );
}

function Delete({ aid }: { aid: string }) {
  const a = useDesign((s) => artboard(s, aid));
  return (
    <Dialog open onClose={closeDialog} title={`Delete ${a?.title || aid}?`} kicker="DESIGN · ARTBOARD" testid="design-delete-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="danger" onClick={() => void remove(aid)} data-testid="design-delete-yes">Delete it</Button></>}>
      <p>Its files and all {a?.versions.length || 0} version(s) go from the project folder; its open pins are resolved. Export it first to keep a copy.</p>
    </Dialog>
  );
}

function Export() {
  const boards = useDesign((s) => s.data?.artboards || []);
  const busy = useDesign((s) => s.busy === "export");
  const [as, setAs] = useState("folder");
  const [which, setWhich] = useState("");
  return (
    <Dialog open onClose={closeDialog} title="Export" kicker="DESIGN · EXPORT" testid="design-export-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={busy} onClick={() => void exportAs(as, which)} data-testid="design-export-go">Export</Button></>}>
      <div className="ow-list" role="radiogroup" aria-label="Export as">
        {EXPORTS.map(([k, label]) => (
          <label key={k} className="check od-pick"><input type="radio" name="design-export" checked={as === k} onChange={() => setAs(k)} /> {label}</label>
        ))}
      </div>
      <label className="fd-field">
        <span className="rail-label mono">ARTBOARD</span>
        <select className="input" value={which} onChange={(e) => setWhich(e.target.value)}>
          <option value="">All artboards</option>
          {boards.map((a) => <option key={a.id} value={a.id}>{a.title || a.id}</option>)}
        </select>
      </label>
    </Dialog>
  );
}

function copy(text: string): void {
  void navigator.clipboard?.writeText(text).then(() => toast("Copied", "done"), () => toast("Copy it by hand: the clipboard is off here", "info"));
}

function Contrast({ d }: { d: Extract<DesignDialog, { kind: "contrast" }> }) {
  const dot = (p: { aa: boolean; aa_large: boolean }) => (p.aa ? "ok" : p.aa_large ? "warn" : "bad");
  return (
    <Dialog open onClose={closeDialog} title={`Contrast of ${d.aid}`} kicker="DESIGN · WCAG" testid="design-contrast" footer={<Button onClick={closeDialog}>Close</Button>}>
      {d.error ? <p className="og-problems">{d.error}</p> : !d.data ? <p className="muted">checking...</p> : (
        <>
          {d.data.pairs.length > 0 && (
            <table className="dd-contrast mono">
              <thead><tr><th /><th>text</th><th>on</th><th>ratio</th><th /></tr></thead>
              <tbody>
                {d.data.pairs.map((p, i) => (
                  <tr key={i}><td><i className="dd-dot" data-tone={dot(p)} /></td><td>{p.fg}</td><td>{p.bg}</td><td>{p.ratio.toFixed(2)}</td><td>{p.aaa ? "AAA" : p.aa ? "AA" : p.aa_large ? "large" : "fail"}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="muted">{d.data.note}</p>
        </>
      )}
    </Dialog>
  );
}

function Synced({ d }: { d: Extract<DesignDialog, { kind: "synced" }> }) {
  return (
    <Dialog open onClose={closeDialog} title={`Design system: ${d.tokens} token${d.tokens === 1 ? "" : "s"}`} kicker="DESIGN · SYNC" testid="design-sync-dialog"
            footer={<Button variant="primary" onClick={closeDialog}>Done</Button>}>
      <p>Read from <code className="mono">{d.source}</code> and merged into the project's system.json; the next turn designs with it.</p>
      {d.groups.length ? (
        <table className="dd-contrast mono">
          <thead><tr><th>group</th><th>tokens</th></tr></thead>
          <tbody>{d.groups.map(([g, n]) => <tr key={g}><td>{g}</td><td>{n}</td></tr>)}</tbody>
        </table>
      ) : <p className="muted">No tokens were found there.</p>}
      {d.sources.length > 0 && <pre className="dd-lines mono">{d.sources.join("\n")}</pre>}
    </Dialog>
  );
}

export function DesignDialogs() {
  const d = useDesign((s) => s.dialog);
  if (!d) return null;
  if (d.kind === "new") return <NewProject />;
  if (d.kind === "rename") return <Rename aid={d.aid} />;
  if (d.kind === "delete") return <Delete aid={d.aid} />;
  if (d.kind === "export") return <Export />;
  if (d.kind === "contrast") return <Contrast d={d} />;
  if (d.kind === "synced") return <Synced d={d} />;
  if (d.kind === "exported")
    return (
      <Dialog open onClose={closeDialog} title={`Exported: ${d.as}`} kicker="DESIGN · EXPORT" testid="design-exported" footer={<Button variant="primary" onClick={closeDialog}>Done</Button>}>
        <pre className="dd-lines mono">{d.lines.join("\n") || "nothing was written"}</pre>
      </Dialog>
    );
  const cmd = `halo --cwd "${d.path}" "continue from HANDOFF.md"`;
  return (
    <Dialog open onClose={closeDialog} title="Handoff bundle written" kicker="DESIGN · HANDOFF" testid="design-handoff-dialog"
            footer={<><Button onClick={() => copy(d.path)}>Copy the path</Button><Button variant="primary" onClick={closeDialog}>Done</Button></>}>
      <p>The artboards, the design system and HANDOFF.md for the next Halo or Claude Code session:</p>
      <pre className="dd-lines mono" data-testid="design-handoff-path">{d.path}</pre>
      <p className="muted">Continue there with <code className="mono">{cmd}</code></p>
      <Button size="sm" variant="ghost" onClick={() => copy(cmd)}>Copy the command</Button>
    </Dialog>
  );
}
