// The plan's staged note and its Copy (3.0.9.0 R3 for a coach card's plan change; 3.4.0.0 B2: the coach is a pack and
// stages nothing here, so `staged` is only ever cleared): Copy puts the jobs on the clipboard (for `halo orchestra
// approve --file` on a run started with Review the plan before it runs).
import { toast } from "../../../lib/store";
import { plan } from "./store";

export function unstage(): void {
  plan.update(() => ({ staged: "" }));
}

export function copyPlan(): void {
  const text = JSON.stringify({ jobs: plan.get().jobs }, null, 2);
  try {
    navigator.clipboard.writeText(text).then(
      () => toast("The plan's jobs are on the clipboard", "done"),
      () => toast("The clipboard is closed to this page", "error"),
    );
  } catch {
    toast("The clipboard is closed to this page", "error");
  }
}
