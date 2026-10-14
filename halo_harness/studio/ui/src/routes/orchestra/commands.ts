// The Orchestra's palette commands: new run, stop run, open run <id>, focus
// lane N (one per run of the repo and per lane of the open run).
import { goSection } from "../../lib/store";
import { openPanel } from "./bits";
import { focusLane, orch } from "./store";
import { openRun, startOrchestra, stopRun } from "./sync";

export type OrchCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

function inOrchestra(fn: () => void): () => void {
  return () => {
    goSection("orchestra");
    startOrchestra();
    window.setTimeout(fn, 60);
  };
}

export function orchestraCommands(): OrchCommand[] {
  const s = orch.get();
  const out: OrchCommand[] = [
    { id: "orch-new", group: "Orchestra", label: "Orchestra: new run", hint: "write the goal, then Run", run: inOrchestra(() => openPanel("goal")) },
  ];
  if (s.data?.live)
    out.push({ id: "orch-stop", group: "Orchestra", label: "Orchestra: stop run", hint: `run ${s.runId} stops at its next step`, run: () => void stopRun() });
  for (const r of s.runs.slice(0, 30)) {
    out.push({
      id: "orch-open-" + r.run_id,
      group: "Orchestra",
      label: `Orchestra: open run ${r.run_id}`,
      hint: `${r.state} · ${r.goal_what.slice(0, 40)}`,
      run: inOrchestra(() => void openRun(r.run_id)),
    });
  }
  for (const l of s.data?.lanes || []) {
    out.push({
      id: "orch-lane-" + l.lane,
      group: "Orchestra",
      label: `Orchestra: focus lane ${l.lane}`,
      hint: `${l.state} · ${l.title}`,
      run: inOrchestra(() => {
        focusLane(l.lane);
        openPanel("lanes");
      }),
    });
  }
  return out;
}
