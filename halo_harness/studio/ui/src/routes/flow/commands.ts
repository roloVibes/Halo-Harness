// The palette's Flow and Media groups. Flow: new run, open run <id>, answer
// the open gate (accept / redo / stop), stop or resume the run. Media:
// status, scan, quick render -- in the Flow section the Media strips open;
// in Design the panels pop out over the canvas.
import { goSection, studio, toast } from "../../lib/store";
import { showPanel } from "../../lib/workspace/persist";
import { mediaPanels } from "../media/MediaPanels";
import { media, scan } from "../media/store";
import { answerGate, resumeRun, stopRun } from "./actions";
import { openFlowPanel } from "./bits";
import { flow, setView } from "./store";
import { openRun, startFlow } from "./sync";

export type FlowCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

function inFlow(fn: () => void): () => void {
  return () => {
    goSection("flow");
    startFlow();
    window.setTimeout(fn, 60);
  };
}

export function flowCommands(): FlowCommand[] {
  const s = flow.get();
  const out: FlowCommand[] = [
    { id: "flow-new", group: "Flow", label: "Flow: new run", hint: "the Start view: write the brief, then Run", run: inFlow(() => setView("start")) },
  ];
  const gate = s.data?.gate;
  if (gate) {
    const where = gate.artboards?.length ? "flow-renders" : "flow-step";
    out.push(
      { id: "flow-accept", group: "Flow", label: "Flow: answer gate: accept", hint: `${gate.step} round ${gate.round}`, run: () => void answerGate("accept") },
      { id: "flow-redo", group: "Flow", label: "Flow: answer gate: redo...", hint: "write the instruction in the gate card", run: inFlow(() => openFlowPanel(where)) },
      { id: "flow-stop-gate", group: "Flow", label: "Flow: answer gate: stop", hint: `stops run ${s.runId}`, run: () => void answerGate("stop") },
    );
  }
  if (s.data?.live) out.push({ id: "flow-stop", group: "Flow", label: "Flow: stop run", hint: `run ${s.runId} stops at its next step`, run: () => void stopRun() });
  else if (s.data && !s.data.report && s.data.flow.status !== "finished")
    out.push({ id: "flow-resume", group: "Flow", label: "Flow: resume run", hint: `run ${s.runId} from its first unfinished step`, run: () => void resumeRun() });
  for (const r of s.runs.slice(0, 30)) {
    out.push({
      id: "flow-open-" + r.run,
      group: "Flow",
      label: `Flow: open run ${r.run}`,
      hint: `${r.waiting_step ? "waiting on you" : r.status} · ${r.name} · ${r.project || ""}`,
      run: inFlow(() => void openRun(r.run)),
    });
  }
  return out;
}

/** Open a Media panel where it lives: a strip in Flow, a popped-out panel in Design, else go to Flow;
 *  while ComfyUI does not answer, the status card (with the fix) opens instead. */
export function openMedia(want: string): void {
  const section = studio.get().section;
  const down = media.get().status?.reachable === false;
  const id = down ? "media-status" : want; // ComfyUI does not answer: the status card says how to fix it
  if (down && want !== id) toast("ComfyUI does not answer: Media status shows how to point Halo at it", "info", 4500);
  if (section === "design") {
    const spec = mediaPanels(0, "optional").find((p) => p.id === id);
    if (spec) showPanel("design", spec, true);
    return;
  }
  if (section !== "flow") goSection("flow");
  window.setTimeout(() => openFlowPanel(id), section === "flow" ? 0 : 60);
}

export function mediaCommands(): FlowCommand[] {
  return [
    { id: "media-status", group: "Media", label: "Media: status", hint: "ComfyUI: reachable, version, VRAM, cache", run: () => openMedia("media-status") },
    { id: "media-scan", group: "Media", label: "Media: scan", hint: "read the server's models and saved workflows", run: () => void scan() },
    { id: "media-models", group: "Media", label: "Media: models", hint: "image, video, audio, upscale", run: () => openMedia("media-models") },
    { id: "media-render", group: "Media", label: "Media: quick render", hint: "a workflow into a design project", run: () => openMedia("media-render") },
  ];
}
