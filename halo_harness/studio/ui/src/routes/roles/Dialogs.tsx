// The Roles dialogs (3.0.7.0 R2, one at a time: store `dialog`; never a
// browser prompt or confirm): New lineup (a name, and the lineup to start
// from), Duplicate, Delete (asks), Apply (asks, listing the role table it
// writes into ~/.halo/config.json), New bio, Duplicate bio, Delete bio, remove
// a card, and leaving unsaved edits for another lineup.
import { useState, type ReactNode } from "react";
import { Button, Dialog } from "../../lib/ui";
import { applyLineup, deleteLineup, newLineup, removeCard } from "./actions";
import { deleteBio, newBio } from "./bioActions";
import { closeDialog, keyOf, nodeById, roles, useRoles } from "./store";
import { openLineup } from "./sync";
import type { RolesDialog } from "./types";

const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

function NameDialog({ title, kicker, start, from, froms, go, testid, busyKey }: {
  title: string; kicker: string; start: string; from: string; froms?: string[]; go: (name: string, from: string) => void; testid: string; busyKey: string;
}) {
  const [name, setName] = useState(start);
  const [src, setSrc] = useState(from);
  const busy = useRoles((s) => s.busy === busyKey);
  const ok = NAME_RE.test(name.trim());
  const submit = () => ok && !busy && go(name.trim(), src);
  return (
    <Dialog open onClose={closeDialog} title={title} kicker={kicker} testid={testid}
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!ok || busy} onClick={submit} data-testid={`${testid}-go`}>Create</Button></>}>
      <label className="fd-field">
        <span className="rail-label mono">NAME</span>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} data-testid={`${testid}-name`} />
      </label>
      {!ok && name && <p className="og-problems">Letters, digits, - and _ only, starting with a letter or digit.</p>}
      {froms && (
        <label className="fd-field">
          <span className="rail-label mono">START FROM</span>
          <select className="input" value={src} onChange={(e) => setSrc(e.target.value)}>
            {froms.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
      )}
    </Dialog>
  );
}

function Ask({ title, kicker, body, yes, onYes, testid, danger }: { title: string; kicker: string; body: ReactNode; yes: string; onYes: () => void; testid: string; danger?: boolean }) {
  return (
    <Dialog open onClose={closeDialog} title={title} kicker={kicker} testid={testid}
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant={danger ? "danger" : "primary"} onClick={onYes} data-testid={`${testid}-yes`}>{yes}</Button></>}>
      {body}
    </Dialog>
  );
}

function Apply() {
  const cur = useRoles((s) => s.current);
  if (!cur) return null;
  const lines = Object.entries(cur.role_table || {}).map(([r, v]) => `roles.${r}: ${typeof v === "object" && v ? String((v as { model?: string }).model || JSON.stringify(v)) : String(v)}`);
  return (
    <Ask title={`Apply ${cur.name}?`} kicker="ROLES · APPLY" testid="roles-apply-dialog" yes="Apply" onYes={() => void applyLineup()}
         body={<>
           <p>New sessions use this lineup. Studio writes the role table and the active team into ~/.halo/config.json, exactly like halo teams use.</p>
           <pre className="re-diff mono">{[...lines, `team: ${cur.name}`, "roles.enabled: true"].map((l) => "+ " + l).join("\n")}</pre>
         </>} />
  );
}

function body(d: NonNullable<RolesDialog>, lineups: string[], bios: string[]) {
  switch (d.kind) {
    case "new-lineup":
      return <NameDialog title="New lineup" kicker="ROLES · LINEUP" start={d.from && d.from !== "balanced" ? `${d.from}-mine` : "my-lineup"} from={d.from || "balanced"} froms={lineups}
                         go={(n, f) => void newLineup(n, f)} testid="roles-new-dialog" busyKey="new" />;
    case "dup-lineup":
      return <NameDialog title={`Duplicate ${d.from}`} kicker="ROLES · LINEUP" start={`${d.from}-copy`} from={d.from} go={(n, f) => void newLineup(n, f)} testid="roles-dup-dialog" busyKey="new" />;
    case "delete-lineup":
      return <Ask title={`Delete ${d.name}?`} kicker="ROLES · LINEUP" testid="roles-delete-dialog" yes="Delete" danger onYes={() => void deleteLineup(d.name)}
                  body={<p>Removes the lineup file from your {roles.get().scope} scope. Its saved layout stays; a session that uses it falls back to the default model.</p>} />;
    case "apply":
      return <Apply />;
    case "new-bio":
      return <NameDialog title="New agent bio" kicker="ROLES · BIO" start="my-agent" from={d.from} froms={["", ...bios]} go={(n, f) => void newBio(n, f)} testid="roles-new-bio-dialog" busyKey="new-bio" />;
    case "dup-bio":
      return <NameDialog title={`Duplicate ${d.from}`} kicker="ROLES · BIO" start={`${d.from}-mine`} from={d.from} go={(n, f) => void newBio(n, f)} testid="roles-dup-bio-dialog" busyKey="new-bio" />;
    case "delete-bio":
      return <Ask title={`Delete ${d.name}?`} kicker="ROLES · BIO" testid="roles-delete-bio-dialog" yes="Delete" danger onYes={() => void deleteBio(d.name)}
                  body={<p>Removes the bio file from your {roles.get().scope} scope. Cards that name it show "bio not found" until you point them at another.</p>} />;
    case "delete-card": {
      const n = nodeById(roles.get(), d.node);
      return <Ask title={`Remove ${n ? keyOf(n) : "this card"}?`} kicker="ROLES · CARD" testid="roles-delete-card" yes="Remove" danger onYes={() => removeCard(d.node)}
                  body={<p>The slot leaves the lineup ({n?.agent} as {n ? keyOf(n) : ""}). The bio stays. Ctrl+Z puts it back; Save keeps the change.</p>} />;
    }
    case "discard":
      return <Ask title="Leave your unsaved edits?" kicker="ROLES · UNSAVED" testid="roles-discard" yes={`Open ${d.then}`}
                  onYes={() => (closeDialog(), void openLineup(d.then, true))} body={<p>{roles.get().name} has edits you did not save. Opening {d.then} drops them (Cancel, then Save, keeps them).</p>} />;
  }
}

export function RolesDialogs() {
  const d = useRoles((s) => s.dialog);
  const lineups = useRoles((s) => s.lineups.map((l) => l.name).join("\n"));
  const bios = useRoles((s) => s.bios.map((b) => b.name).join("\n"));
  if (!d) return null;
  return body(d, lineups.split("\n").filter(Boolean), bios.split("\n").filter(Boolean)) ?? null;
}
