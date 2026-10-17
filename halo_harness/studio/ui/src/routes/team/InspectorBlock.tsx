// The Team Inspector's block and member faces (3.0.8.0 R2). Block: its
// status (path, kind, claims mode, the ledger, every holder with its key,
// state and expiry) and its change lines from `GET team/blocks/<id>/changes`
// (newest first, More pages on with `next`). Member: name, lineup (a link
// that opens Roles on that lineup), role, harness, and the stages it is in.
import { Button } from "../../lib/ui";
import { openInRoles, select } from "./actions";
import { blockOf, claimState, doc, memberOf, rows, useTeam } from "./store";
import { loadChanges } from "./sync";

const when = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function BlockFace({ id }: { id: string }) {
  const b = useTeam((s) => blockOf(s, id));
  const spec = useTeam((s) => doc(s)?.blocks.find((x) => x.id === id));
  const changes = useTeam((s) => (s.changes?.block === id ? s.changes : null));
  const d = useTeam(doc);
  const users = (d?.workflow.stages || []).filter((x) => x.reads.includes(id) || x.writes.includes(id) || x.trigger === `block_change:${id}`);
  if (!spec) return <p className="muted">Block {id} is not in the team file any more.</p>;
  const claim = claimState(b);
  const list = [...(changes?.list || [])].reverse();
  return (
    <div className="tm-face" data-testid="team-block-face" data-block={id} data-claim={claim}>
      <div className="tm-face-head">
        <b className="tm-face-title">{id}</b>
        <span className="og-chip mono tm-claim" data-claim={claim}>{claim === "writing" ? "someone writes" : claim === "held" ? "held" : "free"}</span>
      </div>
      <dl className="tm-kv mono">
        <div><dt>path</dt><dd>{spec.path}</dd></div>
        <div><dt>kind</dt><dd>{spec.kind}</dd></div>
        <div><dt>claims</dt><dd>{spec.claims}</dd></div>
        <div><dt>ledger</dt><dd title={b?.ledger}>{b?.ledger ? b.ledger.replace(/^.*[\\/](?=[^\\/]+[\\/]\.halo-block)/, "") : "-"}</dd></div>
        <div><dt>changes</dt><dd>{b?.changes_count ?? 0}</dd></div>
        <div><dt>stages</dt><dd>{users.map((x) => x.id).join(", ") || "-"}</dd></div>
      </dl>
      <div className="glance-kicker mono">HOLDERS</div>
      {b?.holders.length ? (
        <ul className="tm-holders" data-testid="team-holders">
          {b.holders.map((h) => (
            <li key={h.holder + h.key} data-state={h.state}>
              <b className="mono">{h.holder}</b> <span className="mono">{h.key}</span>
              <span className="muted mono"> · {h.state} · until {when(h.expires)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Nobody holds a part of it now. A member claims a part by writing it while its stage runs; the stage's claims end with it.</p>
      )}
      <div className="glance-kicker mono">CHANGES</div>
      {changes?.error && <p className="tm-error">{changes.error}</p>}
      {list.length ? (
        <ul className="tm-changes" data-testid="team-changes">
          {list.map((c, i) => (
            <li key={`${c.ts}-${c.key}-${i}`} data-testid="team-change">
              <span className="mono muted">{when(c.ts)}</span> <b className="mono">{c.by}</b> <span className="mono">{c.op}</span> <span className="mono">{c.key}</span>
              {c.summary && <span className="muted"> · {c.summary}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No change lines yet.</p>
      )}
      {changes && !changes.done && (
        <Button size="sm" variant="ghost" onClick={() => void loadChanges(id, true)} data-testid="team-changes-more">More</Button>
      )}
    </div>
  );
}

export function MemberFace({ name }: { name: string }) {
  const m = useTeam((s) => memberOf(s, name));
  const all = useTeam(rows);
  const inStages = all.filter((r) => r.members.includes(name));
  if (!m) return <p className="muted">Member {name} is not in the team file any more.</p>;
  return (
    <div className="tm-face" data-testid="team-member-face" data-member={name}>
      <div className="tm-face-head">
        <b className="tm-face-title">{m.name}</b>
        <span className="og-chip mono">{m.harness ? `on ${m.harness}` : "here"}</span>
      </div>
      <dl className="tm-kv mono">
        <div>
          <dt>lineup</dt>
          <dd>
            <button className="og-link mono" onClick={() => openInRoles(m.lineup)} title="Open this lineup in Roles" data-testid="team-member-lineup">{m.lineup}</button>
          </dd>
        </div>
        <div><dt>role</dt><dd>{m.role}</dd></div>
        <div><dt>harness</dt><dd>{m.harness ? `${m.harness} (its task goes out through the fleet's run_task)` : "here (halo -p in the repo)"}</dd></div>
      </dl>
      <div className="glance-kicker mono">STAGES</div>
      {inStages.length ? (
        <ul className="tm-stagelist">
          {inStages.map((r) => (
            <li key={r.id}>
              <button className="og-link mono" onClick={() => select({ kind: "stage", id: r.id })}>{r.id}</button>
              <span className="og-chip mono tm-run-state" data-state={r.state}>{r.state}</span>
              {r.lead === name && <span className="muted mono"> lead</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">In no stage yet: list it under a stage's members (or play an alias a stage names).</p>
      )}
    </div>
  );
}
