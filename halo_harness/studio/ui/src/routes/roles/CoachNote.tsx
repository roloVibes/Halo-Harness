// The note on top of the bio form after a coach card's Apply (3.0.9.0 R3):
// which field it filled in, with what, from which run. The draft holds the
// change; Save bio keeps it, Undo the change puts the bio's own value back.
import { Button } from "../../lib/ui";
import { openBio } from "./bioActions";
import { roles } from "./store";

const shown = (v: unknown) => (Array.isArray(v) ? v.join(", ") || "(none)" : String(v));

export function CoachNote({ field, value, run }: { field: string; value: unknown; run: string }) {
  const close = () => roles.update(() => ({ coachHint: null }));
  const undo = () => {
    const name = roles.get().bio;
    close();
    void openBio(name);
  };
  return (
    <div className="cc-note" role="status" data-testid="bio-coach-note" data-field={field}>
      <span className="glance-kicker mono">FROM THE COACH · RUN {run}</span>
      <span>
        <b className="mono">{field}</b> = <span className="mono" data-testid="bio-coach-value">{shown(value)}</span> is filled in below.
        Save bio keeps it.
      </span>
      <span className="cc-note-actions">
        <Button size="sm" variant="ghost" onClick={undo} data-testid="bio-coach-undo">Undo the change</Button>
        <Button size="sm" variant="ghost" onClick={close} aria-label="Close the note">Close</Button>
      </span>
    </div>
  );
}
