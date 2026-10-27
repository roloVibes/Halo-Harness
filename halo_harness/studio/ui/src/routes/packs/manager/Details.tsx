// pm-details (3.2.0.0 R6): the selected pack, as `halo pack inspect` reads it --
// its description, author and license; the extension API and Halo ranges
// beside this Halo's; each pack it requires and whether that is met; what
// keeps it from running here (the doctor's words); each permission it
// requests with a Grant toggle (an enabled pack: `halo pack grant`; a
// disabled one: picked for its Enable); what it contributes (the block
// inspect prints) with links to its section, its Roles group and each
// workflow's Run; and its health, the doctor's rows.
import { Empty } from "../../../lib/ui";
import { goSection, type SectionId } from "../../../lib/store";
import { applyEdit } from "../../../shell/edit";
import { runWorkflow } from "../../orchestra/workflowRun";
import { cli, grantPack, selected, togglePick, useMgr } from "./store";
import type { PackRow, Permission } from "./types";

const author = (a: unknown) => (typeof a === "string" ? a : a && typeof a === "object" ? String((a as { name?: string }).name || "") : "");

function Grant({ p, perm }: { p: PackRow; perm: Permission }) {
  const busy = useMgr((s) => !!s.busy);
  const picked = useMgr((s) => (s.picks[p.id] || []).includes(perm.name));
  const on = p.enabled ? perm.granted : picked;
  const why = !p.installed ? "install it first" : p.enabled ? cli.grant(p.id, perm.name, !perm.granted) : "given when you press Enable";
  const flip = (v: boolean) => (p.enabled ? void grantPack(p.id, perm.name, v) : togglePick(p.id, perm.name, v));
  return (
    <li className="pm-perm" data-testid="pm-perm" data-name={perm.name} data-granted={perm.granted || undefined}>
      <label className="og-switch mono" title={why}>
        <input type="checkbox" checked={on} disabled={busy || !p.installed} onChange={(e) => flip(e.target.checked)} data-testid="pm-grant" data-name={perm.name} />
        {perm.name}
      </label>
      <span className="muted">{perm.needed_by.length ? perm.needed_by.join(", ") : "its own code"}</span>
      <span className="mono pm-perm-state">{perm.granted ? "granted" : p.enabled ? "not granted" : picked ? "picked" : "not granted"}</span>
    </li>
  );
}

function openRoles(name: string): void {
  if (name) void applyEdit({ kind: "lineup", name, text: `lineup:${name}` });
  else goSection("roles");
}

function Links({ p }: { p: PackRow }) {
  return (
    <div className="pm-links" data-testid="pm-links">
      {p.running && p.sections.map((s) => (
        <button key={s.id} className="og-link" onClick={() => goSection(s.id as SectionId)} data-testid="pm-open-section">open {s.title}</button>
      ))}
      {p.running && p.lineups.length > 0 && (
        <button className="og-link" onClick={() => openRoles(p.lineups[0].name)} data-testid="pm-open-roles">Roles: {p.lineups[0].name}</button>
      )}
      {p.running && p.workflows.map((w) => (
        <button key={w.ref} className="og-link" onClick={() => runWorkflow(w)} data-testid="pm-details-run" data-ref={w.ref}>Run {w.name}</button>
      ))}
      {!p.running && <span className="muted">{p.installed ? "Enable it and its section, lineups and workflows open from here." : "Install and enable it to open its section, lineups and workflows."}</span>}
    </div>
  );
}

export function DetailsDetail() {
  const p = useMgr((s) => selected(s));
  const loaded = useMgr((s) => s.loaded);
  if (!loaded) return null; // 3.3.2.0 R3: Installed says "reading the packs..." once
  if (!p) return <Empty title="Pick a pack" body="Click a pack in Installed or a name in Sources: its details show here." testid="pm-details-empty" />;
  const api = p.compat.some((c) => c.includes("extension API")) ? "warn" : "ok";
  return (
    <div className="pm-details" data-testid="pm-details-body" data-id={p.id}>
      <header className="pm-det-head">
        <div className="glance-kicker mono">{p.id.toUpperCase()} · {p.version}</div>
        <h3 className="pm-det-title">{p.name}</h3>
        <p>{p.description}</p>
        <p className="muted mono">{[author(p.author), p.license, p.installed ? p.state : "not installed"].filter(Boolean).join(" · ")}</p>
      </header>
      <dl className="pk-art-kv pm-kv">
        <div className="pk-art-kv-row"><dt>extension API</dt><dd data-state={api} data-testid="pm-api">{p.halo_api}; this Halo has {p.this_api}</dd></div>
        <div className="pk-art-kv-row"><dt>Halo</dt><dd>{p.halo}; this is {p.this_halo}</dd></div>
        <div className="pk-art-kv-row"><dt>requires</dt><dd data-testid="pm-requires">
          {p.requires.length ? p.requires.map((r) => `${r.pack} ${r.version}: ${r.met ? "met" : r.have ? `${r.have} is ${r.running ? "running" : "not running"}` : "not installed"}`).join("; ") : "no other pack"}
        </dd></div>
      </dl>
      <div className="rail-label mono">WHAT KEEPS IT FROM RUNNING HERE</div>
      {p.compat.length ? (
        <ul className="pm-compat" data-testid="pm-compat">{p.compat.map((c) => <li key={c}>{c}</li>)}</ul>
      ) : (
        <p className="muted" data-testid="pm-compat-none">Nothing: it runs here once enabled.</p>
      )}
      <div className="rail-label mono">PERMISSIONS IT REQUESTS</div>
      {p.permissions.length ? <ul className="pm-perms">{p.permissions.map((x) => <Grant key={x.name} p={p} perm={x} />)}</ul> : <p className="muted">None.</p>}
      <div className="rail-label mono">WHAT IT CONTRIBUTES</div>
      <pre className="pm-lines mono" data-testid="pm-contributes">{p.contributes_lines.slice(1).map((l) => l.replace(/^ {2}/, "")).join("\n") || "offers: " + p.problems.join("; ")}</pre>
      <Links p={p} />
      <div className="rail-label mono">HEALTH (HALO PACK DOCTOR)</div>
      {p.health.length ? (
        <ul className="pm-health">
          {p.health.map((h) => (
            <li key={h.check + h.text} data-severity={h.severity} data-testid="pm-health-row">
              <span className="mono">{h.severity === "blocks" ? "[ERROR]" : "[WARN]"}</span> {h.text}{h.fix ? <span className="muted"> -&gt; {h.fix}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{p.installed ? "No problem." : "Checked once it is installed."}</p>
      )}
    </div>
  );
}

export function DetailsGlance() {
  const p = useMgr((s) => selected(s));
  return (
    <div className="glance">
      <div className="glance-kicker mono">DETAILS</div>
      <div className="glance-text">{p ? p.name : "no pack picked"}</div>
      <div className="glance-hint">{p ? `${p.granted.length}/${p.requested.length} granted · ${p.compat.length} warning(s)` : "click one in Installed or Sources"}</div>
    </div>
  );
}
