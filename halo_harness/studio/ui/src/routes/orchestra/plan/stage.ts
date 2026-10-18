// A coach card's plan change, staged (3.0.9.0 R3): the Orchestra section
// opens the run, the plan editor loads its plan (the approved one, else the
// lead's split) and takes the change as one undo step, the lane selected.
// The run already ran, so nothing is sent: the bar says STAGED, Copy puts
// the jobs on the clipboard (for `halo orchestra approve --file` on a run
// started with Review the plan before it runs) and Back returns to the run.
import { goSection, toast } from "../../../lib/store";
import { openRun } from "../sync";
import { loadPlan } from "./actions";
import { plan } from "./store";
import type { PlanJob } from "./types";

function withoutLane(jobs: PlanJob[], id: string): PlanJob[] {
  return jobs.filter((j) => j.id !== id).map((j) => ({
    ...j, after: (j.after || []).filter((a) => a !== id), handoff: { ...(j.handoff || {}), needs: (j.handoff?.needs || []).filter((n) => n.from !== id) },
  }));
}

export async function stagePlan(run: string, field: string, value: unknown, text: string): Promise<void> {
  goSection("orchestra");
  await openRun(run, true);
  await loadPlan(run);
  const s = plan.get();
  const [job, key] = field.split(".");
  if (!s.jobs.some((j) => j.id === job)) {
    toast(`The plan of run ${run} has no ${job}`, "error", 5000);
    return;
  }
  const jobs = key === "drop" ? withoutLane(s.jobs, job)
    : s.jobs.map((j) => (j.id === job ? { ...j, after: Array.isArray(value) ? (value as string[]) : [] } : j));
  // one undo step, set in place (edit() would send it); `staged` last: it is what shows the editor
  plan.update(() => ({ jobs, past: [...s.past, s.jobs], future: [], sel: key === "drop" ? jobs[0]?.id || "" : job, staged: text || "a change from the coach" }));
  toast(`Staged on the plan of run ${run}: ${field}. The run already ran: Copy the plan for a new run.`, "info", 6000);
}

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
