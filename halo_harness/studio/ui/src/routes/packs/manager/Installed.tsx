// pm-installed (3.2.0.0 R6): every pack here, one row each -- its id, name and
// version, enabled or not, the grants given of the ones it requests, its
// health (the doctor's rows for it) and what keeps it from running here (the
// doctor's words) -- with Enable (the grants picked in Details), Disable,
// Update and Remove. Remove asks first, naming what goes, what stays and the
// command it runs. A click on a row selects the pack for Details, Settings
// and Templates. Under the rows: the last action's lines, as `halo pack` printed them.
// 3.2.0.0 R7: Update asks first, showing what `halo pack update <id> --dry-run`
// says (its migration notes, the files and settings that change); Rollback
// (shown once an update kept the version before) runs `halo pack rollback <id>`.
// 3.3.10.0 R2: a pack with policy hooks shows its armed policies and the last verdict (pm-policy).
import { useState } from "react";
import { Button, Dialog, Empty } from "../../../lib/ui";
import { BundlesGroup } from "./Bundles"; // 3.3.7.0 R5: the bundles, each a tick with its verdict
import { GrantDialog } from "./GrantDialog"; // 3.4.1.2: a grant that runs a pack's code, the owner's yes first
import { cli, disablePack, enablePack, mgr, previewUpdate, removePack, rollbackPack, selectPack, serviceAct, updatePack, useMgr } from "./store";
import type { PackRow, PolicyBlock, ServiceRow } from "./types";

const NONE: string[] = [];

function stateWord(p: PackRow): string {
  return p.running ? "enabled" : p.state;
}

/** 3.3.10.0 R2: the armed policies and the last verdict a session got (`halo pack policy status`, `log`). */
function PolicyChip({ b, id }: { b: PolicyBlock; id: string }) {
  const counts = Object.entries(b.counts).map(([k, n]) => `${k} ${n}`).join(", ");
  const title = [`mode: ${b.mode || "none"}`, `verdicts: ${counts || "none yet"}`, `halo pack policy log ${id}`].join("\n");
  return (
    <span className="og-chip mono pm-policy" title={title} data-testid="pm-policy" data-armed={b.armed.length || undefined}>
      {b.armed.length ? `armed: ${b.armed.join(", ")}` : "no policy armed"}{b.last ? ` · last: ${b.last}` : ""}
    </span>
  );
}

/** 3.3.13.0 R3: a service the supervisor runs for the pack: its state line, with Start or Stop. */
function ServiceChip({ s, id, busy }: { s: ServiceRow; id: string; busy: boolean }) {
  const running = s.state === "running";
  const cmd = `halo supervise service ${running ? "stop" : "start"} ${s.key}`;
  return (
    <span className="pm-service" data-testid="pm-service" data-state={s.state} data-key={s.key}>
      <span className={`og-chip mono${running ? "" : " pm-warn"}`} title={s.description}>service {s.line}</span>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void serviceAct(id, s.name, running ? "stop" : "start")}
              title={`${cmd}: the running supervisor ${running ? "stops" : "starts"} it at its next tick`} data-testid="pm-service-act">
        {running ? "Stop" : "Start"}
      </Button>
    </span>
  );
}

function Row({ p, on }: { p: PackRow; on: boolean }) {
  const busy = useMgr((s) => !!s.busy);
  const picks = useMgr((s) => s.picks[p.id] || NONE); // a stable empty list: a new [] per read re-renders forever
  const warn = p.compat[0] || "";
  const health = p.health.length;
  const notes = (p.notes || []).length; // 3.3.10.0 R3: the doctor's info rows, counted apart
  return (
    <li className="pm-row" data-on={on || undefined} data-state={p.running ? "running" : p.enabled ? "enabled" : "disabled"}
        data-testid="pm-installed-row" data-id={p.id}>
      <button className="pm-row-main" aria-pressed={on} onClick={() => selectPack(p.id)} title={p.description}>
        <span className="pm-row-id mono">{p.id}</span>
        <span className="pm-row-name">{p.name}</span>
        <span className="pm-row-ver mono muted">{p.version}</span>
        {p.ships && (
          <span className="og-chip mono pm-warn" title={`${p.id} ${p.version} is older than the ${p.ships} this Halo ships: ${cli.update(p.id)}`} data-testid="pm-ships">
            {p.ships} available
          </span>
        )}
        <span className="og-chip mono pm-state" data-testid="pm-state">{stateWord(p)}</span>
        <span className="og-chip mono" title={p.requested.length ? `requests: ${p.requested.join(", ")}` : "it requests no permissions"} data-testid="pm-grants">
          {p.granted.length}/{p.requested.length} granted
        </span>
        {health > 0 && (
          <span className="og-chip mono pm-warn" title={p.health.map((h) => h.text).join("\n")} data-testid="pm-health-count">
            {health} doctor line{health === 1 ? "" : "s"}
          </span>
        )}
        {notes > 0 && (
          <span className="og-chip mono muted" title={p.notes.map((h) => h.text).join("\n")} data-testid="pm-notes-count">
            {notes} note{notes === 1 ? "" : "s"}
          </span>
        )}
        {(p.setup_waiting || 0) > 0 && (
          <span className="og-chip mono muted" title={`halo setup ${p.id} opens them`} data-testid="pm-setup-waiting">
            setup waiting
          </span>
        )}
        {p.policy && <PolicyChip b={p.policy} id={p.id} />}
        {warn && <span className="pm-row-warn" data-testid="pm-row-warn">{warn}</span>}
      </button>
      <span className="pm-row-acts">
        {p.enabled && (p.services || []).map((s) => <ServiceChip key={s.key} s={s} id={p.id} busy={busy} />)}
        {!p.enabled && (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void enablePack(p.id, picks)} title={cli.enable(p.id, picks)} data-testid="pm-enable">
            Enable{picks.length ? ` (${picks.length} grant${picks.length === 1 ? "" : "s"})` : ""}
          </Button>
        )}
        {p.enabled && (
          <Button size="sm" disabled={busy} onClick={() => void disablePack(p.id)} title={`${cli.disable(p.id)}: nothing of it runs; its grants are cleared`} data-testid="pm-disable">
            Disable
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy || !p.installed} onClick={() => void previewUpdate(p.id)} title={`${cli.update(p.id)} (shows ${cli.update(p.id, true)} first)`} data-testid="pm-update">
          Update
        </Button>
        {p.previous && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void rollbackPack(p.id)} title={`${cli.rollback(p.id)}: back to ${p.previous}`} data-testid="pm-rollback">
            Roll back to {p.previous}
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => mgr.update(() => ({ removing: p.id }))} title={`${cli.remove(p.id, false)} (asks first)`} data-testid="pm-remove">
          Remove
        </Button>
      </span>
    </li>
  );
}

function RemoveDialog() {
  const id = useMgr((s) => s.removing);
  const [keep, setKeep] = useState(false);
  const close = () => (mgr.update(() => ({ removing: "" })), setKeep(false));
  if (!id) return null;
  const yes = async () => {
    close();
    await removePack(id, keep);
  };
  return (
    <Dialog open onClose={close} title={`Remove ${id}?`} kicker="PACKS · REMOVE" testid="pm-remove-dialog"
            cost={{ does: `removes ${id}: the files its install or update wrote that still hold what it wrote`, costs: "nothing: no model call",
                    writes: keep ? "the pack's own files go; its record and grants stay for a later install" : "the pack's own files, its record and its grants go; your files stay" }}
            footer={<><Button onClick={close}>Cancel</Button><Button variant="danger" onClick={() => void yes()} data-testid="pm-remove-yes">Remove</Button></>}>
      <p>Removes the pack's own files: the ones its install or update wrote that still hold what it wrote. A file of its folder you changed stays, and so does everything of yours: your bios and lineups, your settings, the memory folders. Each one is listed after.</p>
      <label className="og-switch mono">
        <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} data-testid="pm-keep-config" />
        Keep its record and grants for a later install
      </label>
      <code className="pk-grant-cmd" data-testid="pm-remove-cmd">{cli.remove(id, keep)}</code>
    </Dialog>
  );
}

function UpdateDialog() {
  const u = useMgr((s) => s.updating);
  const close = () => mgr.update(() => ({ updating: null }));
  if (!u) return null;
  const nothing = u.ok && u.lines.some((l) => l.includes(" is up to date"));
  const yes = async () => {
    close();
    await updatePack(u.id);
  };
  return (
    <Dialog open onClose={close} title={`Update ${u.id}?`} kicker="PACKS · UPDATE" testid="pm-update-dialog"
            cost={u.ok && !nothing ? { does: `replaces ${u.id} with its new version; the one now kept for Roll back`, costs: "nothing: no model call",
                                      writes: "the pack's own files, its record; your files it keeps (listed above)" } : undefined}
            footer={<><Button onClick={close}>{u.ok && !nothing ? "Cancel" : "Close"}</Button>{u.ok && !nothing && <Button variant="primary" onClick={() => void yes()} data-testid="pm-update-yes">Update</Button>}</>}>
      <p>{u.ok ? "What the update does, before anything is replaced: the version kept for Roll back, its migration notes, the settings it renames and your files it keeps." : "The update cannot run:"}</p>
      <pre className="pm-lines mono" data-testid="pm-update-lines">{u.lines.join("\n")}</pre>
      <code className="pk-grant-cmd" data-testid="pm-update-cmd">{cli.update(u.id, !u.ok || nothing)}</code>
    </Dialog>
  );
}

function Last() {
  const last = useMgr((s) => s.last);
  if (!last) return null;
  return (
    <div className="pm-last" data-ok={last.ok || undefined} data-testid="pm-last">
      <div className="rail-label mono">{last.what.toUpperCase()}</div>
      <pre className="pm-lines mono">{last.lines.join("\n")}</pre>
    </div>
  );
}

export function InstalledDetail() {
  const data = useMgr((s) => s.data);
  const error = useMgr((s) => s.error);
  const sel = useMgr((s) => s.sel);
  if (!data) return error ? <Empty title="Studio could not read the packs" body={error} testid="pm-error" /> : <div className="og-wait mono muted">reading the packs...</div>;
  return (
    <div className="pm-installed" data-testid="pm-installed-body">
      {data.packs.length ? (
        <ul className="pm-rows">
          {data.packs.map((p) => (
            <Row key={p.id} p={p} on={p.id === sel} />
          ))}
        </ul>
      ) : (
        <Empty title="No pack is installed here" body="Sources lists the packs you can install: the folders and git urls of packs.sources, and the Documentation Review pack Halo ships." testid="pm-installed-empty" />
      )}
      {data.problems.map((h) => (
        <p key={h.text} className="pm-row-warn">{h.text}{h.fix ? ` -> ${h.fix}` : ""}</p>
      ))}
      <Last />
      <BundlesGroup />
      <RemoveDialog />
      <UpdateDialog />
      <GrantDialog />
    </div>
  );
}

export function InstalledGlance() {
  const n = useMgr((s) => s.data?.packs.length ?? 0);
  const on = useMgr((s) => s.data?.packs.filter((p) => p.running).length ?? 0);
  return (
    <div className="glance">
      <div className="glance-kicker mono">INSTALLED</div>
      <div className="glance-text mono">{n} pack{n === 1 ? "" : "s"}</div>
      <div className="glance-hint">{on} running</div>
    </div>
  );
}
