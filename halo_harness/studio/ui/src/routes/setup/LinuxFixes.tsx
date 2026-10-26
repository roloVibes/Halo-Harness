// setup-linux (3.3.0.0 R3): the fixes a Linux box may be missing, the same
// two the terminal wizard's Linux step applies -- a static ripgrep (rg) in
// ~/.local/bin, and ~/.local/bin on PATH for a non-interactive shell (one
// line in ~/.zshenv or ~/.profile). Listed only when this box lacks one;
// Apply runs them (POST setup/linux-fixes) and the lines say what was
// written. Otherwise one muted line: nothing to fix on this box.
import { Button } from "../../lib/ui";
import { useLoadState, Waiting } from "./BlockFoot";
import { CardLines, send, useCards } from "./cards";
import { NONE, useSetup } from "./store";

export function LinuxFixesDetail() {
  const { ready, error } = useLoadState();
  const needed = useSetup((s) => !!s.data?.linux_fixes.needed);
  const items = useSetup((s) => s.data?.linux_fixes.items || NONE);
  const busy = useCards((s) => s.busy);
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-linux">
      {!needed ? (
        <p className="su-lead muted" data-testid="setup-linux-none">nothing to fix on this box</p>
      ) : (
        <>
          <p className="su-lead muted">This box is missing what halo's tools expect on Linux. Apply does what the terminal wizard's Linux step does:</p>
          <ul className="su-fixes" data-testid="setup-linux-items">
            {items.map((i) => (
              <li key={i.id} className="mono" data-testid="setup-linux-item" data-id={i.id}>
                {i.line}
              </li>
            ))}
          </ul>
          <div className="su-foot-row">
            <Button variant="primary" size="sm" disabled={!!busy} onClick={() => void send("linux", "setup/linux-fixes", {})} data-testid="setup-linux-apply">
              {busy === "linux" ? "Applying..." : "Apply"}
            </Button>
          </div>
        </>
      )}
      <CardLines card="linux" />
    </div>
  );
}

export function LinuxFixesGlance() {
  const n = useSetup((s) => s.data?.linux_fixes.items.length || 0);
  return (
    <div className="glance">
      <div className="glance-kicker mono">LINUX FIXES</div>
      <div className="glance-text">{n ? `${n} to apply` : "nothing to fix"}</div>
      <div className="glance-hint">rg in ~/.local/bin, ~/.local/bin on PATH</div>
    </div>
  );
}
