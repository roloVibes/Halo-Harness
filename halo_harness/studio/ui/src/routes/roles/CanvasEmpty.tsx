// The Roles canvas with nothing on it invites (3.1.5.0 R3): a bracketed
// glass box over the canvas grid -- "Drag a bio here, or New lineup" on an
// open lineup with no cards (a bio dropped anywhere on the canvas becomes
// its first card), and with no lineup open the same box naming Lineups and
// New lineup (a copy of the open or the balanced lineup, opened here).
import { Button } from "../../lib/ui";
import { openDialog, useRoles } from "./store";

function Invite({ title, line, testid }: { title: string; line: string; testid: string }) {
  const name = useRoles((s) => s.name);
  return (
    <div className="rc-invite holo-frame" data-testid={testid}>
      <span className="holo-corners" aria-hidden="true" />
      <div className="glance-kicker mono">ROLES · THE CANVAS</div>
      <b className="rc-invite-title">{title}</b>
      <p className="rc-invite-line muted">{line}</p>
      <Button size="sm" variant="primary" onClick={() => openDialog({ kind: "new-lineup", from: name || "balanced" })} data-testid="roles-invite-new">
        New lineup
      </Button>
    </div>
  );
}

/** An open lineup with no cards: drag a bio here (the drop is the canvas's own), or start a new lineup. */
export function CanvasInvite() {
  return <Invite title="Drag a bio here, or New lineup" line="Pull any bio from the Bios panel onto the canvas: it becomes a card in this lineup, and you set its model and tier from there." testid="roles-canvas-invite" />;
}

/** No lineup open: the same box, pointing at Lineups and New lineup. */
export function NoLineup() {
  const any = useRoles((s) => s.lineups.length);
  return (
    <div className="rc rc-none holo-grid" data-testid="roles-canvas-empty">
      <Invite title="Drag a bio here, or New lineup" testid="roles-canvas-invite"
              line={any ? "Open a lineup in Lineups (or the palette: Roles: open lineup) and its cards land here; or make your own with New lineup." : "Make your first lineup with New lineup: its cards land here, and any bio from the Bios panel can join it."} />
    </div>
  );
}
