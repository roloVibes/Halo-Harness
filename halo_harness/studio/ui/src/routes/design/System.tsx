// design-system (3.0.7.0 R3b): the open project's design system, the token
// sheet every turn reads (system.json): the tokens by group (colours, type,
// spacing, radii, as the classic page listed them; a colour shows its
// swatch), each value editable with Save tokens, then the components and
// where the sheet came from. Sync reads tokens from a codebase folder or a
// web page (POST sync) and shows what it found in a dialog.
import { useEffect, useState } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { saveTokens, syncSystem } from "./more";
import { useDesign } from "./store";

const COLOUR = /^(#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla|oklch)\([^)]*\))$/;
const K = (g: string, n: string) => g + "\u0000" + n;

/** The edits with `key` set to `v` (dropped again when it is back to the saved value). */
function edit(x: Record<string, string>, key: string, v: string, saved: string): Record<string, string> {
  const out = { ...x };
  if (v === saved) delete out[key];
  else out[key] = v;
  return out;
}

function SyncRow() {
  const busy = useDesign((s) => s.busy === "sync");
  const [src, setSrc] = useState("");
  const go = () => void syncSystem(src).then((ok) => ok && setSrc(""));
  return (
    <div className="dsy-sync">
      <input className="input mono" value={src} onChange={(e) => setSrc(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()}
             placeholder="a folder path or a web page address" aria-label="Sync the design system from" data-testid="design-sync-source" />
      <Button size="sm" variant="primary" disabled={busy || !src.trim()} onClick={go} data-testid="design-sync">{busy ? "Syncing..." : "Sync"}</Button>
    </div>
  );
}

export function SystemDetail() {
  const sys = useDesign((s) => s.data?.system || null);
  const open = useDesign((s) => !!s.data);
  const [edits, setEdits] = useState<Record<string, string>>({});
  useEffect(() => setEdits({}), [sys]);
  if (!open) return <Empty title="No project open" body="Pick one in Projects: its design system shows here." />;
  const groups = Object.entries(sys?.tokens || {});
  const comps = (sys?.components || []).map((c) => (typeof c === "string" ? c : c?.name || "")).filter(Boolean);
  const changed = Object.keys(edits).length;
  return (
    <div className="dsy">
      <SyncRow />
      {!groups.length && <p className="muted dsy-empty">No design system yet. Sync one from a codebase or a web page above, or ask for tokens in a turn.</p>}
      {groups.map(([g, vals]) => (
        <section key={g} className="dsy-group">
          <div className="dsy-head mono"><span>{g}</span><span className="muted">{Object.keys(vals).length}</span></div>
          {Object.entries(vals).map(([name, value]) => {
            const v = edits[K(g, name)] ?? String(value);
            return (
              <div key={name} className="dsy-token" data-testid="design-token" data-group={g} data-name={name}>
                <i className="dsy-swatch" data-none={!COLOUR.test(v.trim()) || undefined} style={COLOUR.test(v.trim()) ? { background: v.trim() } : undefined} />
                <code className="mono">{name}</code>
                <input className="input mono" value={v} aria-label={`${g} ${name}`}
                       onChange={(e) => setEdits((x) => edit(x, K(g, name), e.target.value, String(value)))} />
              </div>
            );
          })}
        </section>
      ))}
      {groups.length > 0 && (
        <div className="dsy-save">
          <span className="muted">{changed ? `${changed} change(s)` : "edit a value to change it"}</span>
          <span className="spacer" />
          {changed > 0 && <Button size="sm" variant="ghost" onClick={() => setEdits({})}>Undo</Button>}
          <Button size="sm" variant="primary" disabled={!changed} onClick={() => void saveTokens(edits)} data-testid="design-tokens-save">Save tokens</Button>
        </div>
      )}
      {comps.length > 0 && (
        <section className="dsy-group">
          <div className="dsy-head mono"><span>components</span><span className="muted">{comps.length}</span></div>
          <div className="dsy-chips">{comps.slice(0, 60).map((c) => <span key={c} className="og-chip mono">{c}</span>)}</div>
        </section>
      )}
      {(sys?.sources || []).length > 0 && (
        <section className="dsy-group">
          <div className="dsy-head mono"><span>sources</span></div>
          {(sys?.sources || []).map((s) => <div key={s} className="mono muted dsy-src">{s}</div>)}
        </section>
      )}
    </div>
  );
}

export function SystemGlance() {
  const sys = useDesign((s) => s.data?.system || null);
  const groups = Object.values(sys?.tokens || {});
  const colours = Object.values(sys?.tokens || {}).flatMap((v) => Object.values(v)).filter((v) => COLOUR.test(String(v).trim())).slice(0, 8);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={groups.length} label="groups" />
        <Metric value={groups.reduce((n, v) => n + Object.keys(v).length, 0)} label="tokens" />
      </div>
      {colours.length > 0 && <div className="dsy-chips">{colours.map((c, i) => <i key={i} className="dsy-swatch" style={{ background: String(c).trim() }} />)}</div>}
    </div>
  );
}

export function useSystemMotion(): MotionState {
  const syncing = useDesign((s) => s.busy === "sync");
  const any = useDesign((s) => Object.keys(s.data?.system?.tokens || {}).length > 0);
  return syncing ? "working" : any ? "idle" : "none";
}
