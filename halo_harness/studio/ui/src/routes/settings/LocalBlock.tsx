// Settings -> Local, the block above the group's rows (3.3.6.0 R5): the changes Halo made to local models' profiles
// (the steward, the ledger's dialect refinements, you, the bench), each with its scope picker (keep preselected for
// yours; until halo exits; until the session ends) and Revert -- the same list as Local -> Benchmarks' third block
// (routes/local/ChangesList.tsx). The rows below stay generic.
import { goSection } from "../../lib/store";
import { Button } from "../../lib/ui";
import { ChangesList } from "../local/ChangesList";
import { goto } from "../local/pages";

export function LocalBlock() {
  const open = () => {
    goto("benchmarks");
    goSection("local");
  };
  return (
    <section className="st-ollama" data-testid="settings-local-block" aria-label="Changes to local models">
      <div className="st-ollama-row">
        <b>Changes to local models</b>
        <span className="muted">each with its scope: keep, until halo exits, until the session ends</span>
        <span className="spacer" />
        <Button size="sm" onClick={open} data-testid="settings-local-open">Open Local -&gt; Benchmarks</Button>
      </div>
      <ChangesList />
    </section>
  );
}
