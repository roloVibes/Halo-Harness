// The Team section's dialogs (3.0.8.0 R2): Stop asks for a reason on a card
// (`POST team/stop`); Validate shows the file's problems and every lineup
// preflight finding with its fix; "Team: open file" shows where the team
// file is (repo or user scope), with Copy. 3.0.9.0 R3: Coach shows the run's
// coach cards (lib/coach).
import { useState } from "react";
import { CoachCards } from "../../lib/coach/CoachCards";
import { Button, Dialog } from "../../lib/ui";
import { applySuggestion } from "../orchestra/coachApply";
import { copyText, stopRun } from "./actions";
import { closeDialog, useTeam } from "./store";
import type { Finding } from "./types";

function StopDialog() {
  const [reason, setReason] = useState("");
  const busy = useTeam((s) => s.busy === "stop");
  const run = useTeam((s) => s.board?.run || "");
  const go = () => void stopRun(reason.trim());
  return (
    <Dialog open onClose={closeDialog} title="Stop the run?" kicker={`TEAM · RUN ${run}`} testid="team-stop-dialog"
            footer={<>
              <Button variant="ghost" onClick={closeDialog}>Keep it running</Button>
              <Button variant="danger" disabled={busy} onClick={go} data-testid="team-stop-confirm">Stop the run</Button>
            </>}>
      <p>Every stage that is not done is skipped; a member that is running finishes its call first. The reason lands in the run's log.</p>
      <input className="input" placeholder="why (optional): stopped in Studio" value={reason} onChange={(e) => setReason(e.target.value)}
             onKeyDown={(e) => e.key === "Enter" && go()} aria-label="Reason" data-testid="team-stop-reason" />
    </Dialog>
  );
}

function FindingRow({ f }: { f: Finding }) {
  return (
    <li data-severity={f.severity} data-testid="team-finding">
      <span className="og-chip mono" data-severity={f.severity}>{f.severity}</span> {f.text}
      {f.fix && <div className="muted">fix: {f.fix}</div>}
    </li>
  );
}

function ValidateDialog({ ok, problems, preflight }: { ok: boolean; problems: string[]; preflight: Finding[] }) {
  return (
    <Dialog open onClose={closeDialog} title={ok ? "The team is ready to run" : "The team has problems"} kicker="TEAM · VALIDATE" testid="team-validate-dialog"
            footer={<Button variant="primary" onClick={closeDialog}>Close</Button>}>
      <p className="mono" data-testid="team-validate-ok" data-ok={ok || undefined}>{ok ? "no problem, no blocking finding" : `${problems.length} problem${problems.length === 1 ? "" : "s"} in the file`}</p>
      {problems.length > 0 && (
        <ul className="tm-dialog-list" data-testid="team-validate-problems">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      <div className="glance-kicker mono">LINEUP PREFLIGHT · EVERY MEMBER THAT WORKS HERE</div>
      {preflight.length ? (
        <ul className="tm-dialog-list">{preflight.map((f) => <FindingRow key={f.id} f={f} />)}</ul>
      ) : (
        <p className="muted">Every member's lineup resolves: models, bios and tools.</p>
      )}
    </Dialog>
  );
}

function FileDialog() {
  const info = useTeam((s) => s.info);
  const path = info?.path || "";
  return (
    <Dialog open onClose={closeDialog} title="The team file" kicker={`TEAM · ${info?.source === "user" ? "USER SCOPE" : "THIS REPO"}`} testid="team-file-dialog"
            footer={<>
              <Button variant="ghost" onClick={closeDialog}>Close</Button>
              <Button variant="primary" disabled={!path} onClick={() => void copyText(path)} data-testid="team-file-copy">Copy</Button>
            </>}>
      <p>{info?.found ? "Open it in your editor; Studio reads it again on the next look." : "There is no team file yet; this is where Make my first team writes it."}</p>
      <input className="input mono" readOnly value={path} onFocus={(e) => e.currentTarget.select()} aria-label="Path" data-testid="team-file-path" />
      {info?.root && <p className="muted mono">repo: {info.root}</p>}
    </Dialog>
  );
}

export function TeamDialogs() {
  const d = useTeam((s) => s.dialog);
  if (!d) return null;
  if (d.kind === "stop") return <StopDialog />;
  if (d.kind === "validate") return <ValidateDialog ok={d.ok} problems={d.problems} preflight={d.preflight} />;
  if (d.kind === "coach")
    return (
      <Dialog open onClose={closeDialog} title="The coach" kicker={`TEAM · RUN ${d.run}`} testid="team-coach-dialog"
              footer={<Button variant="ghost" onClick={closeDialog}>Close</Button>}>
        <CoachCards kind="team" run={d.run} onEdit={applySuggestion} />
      </Dialog>
    );
  return <FileDialog />;
}
