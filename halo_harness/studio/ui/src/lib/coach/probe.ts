// The coach's probe in Studio (3.1.6.0 R2; halo_harness/orchestra/coach_probe.py).
// The Probe button asks POST orchestra/<run>/coach/probe for the cost line
// ("probe: N runs, up to $X", nothing runs); the confirm starts it
// ({confirm: true}: the probe runs on a thread in Studio, never in the
// console's one run slot). Its step lines come over the live feed as
// `orchestra_state` frames carrying `probe_of` (studio/coach_probe_job.py),
// and the run's card is read every few seconds while it runs (the feed may be
// shut); when it ends the card is read again, and the probe's card leads it.
import { api, ApiError } from "../api";
import { onEvent } from "../events";
import { toast } from "../store";
import { coach, keyOf, loadCoach, routeOf, type ProbeUi } from "./store";
import type { ProbeEstimate } from "./types";

const POLL_MS = 3000;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const timers: Record<string, number> = {};
let fed = false;

function set(run: string, fields: Partial<ProbeUi>): void {
  const key = keyOf("orchestra", run);
  coach.update((s) => ({ probe: { ...s.probe, [key]: { ...s.probe[key], ...fields } } }));
}

export const probeUi = (run: string): ProbeUi => coach.get().probe[keyOf("orchestra", run)] || {};

function running(run: string): boolean {
  const p = coach.get().runs[keyOf("orchestra", run)]?.result?.probe;
  return p?.state === "running" || !!p?.live;
}

function poll(run: string): void {
  window.clearTimeout(timers[run]);
  timers[run] = window.setTimeout(async () => {
    await loadCoach("orchestra", run, true);
    if (running(run)) poll(run);
    else set(run, { line: "" });
  }, POLL_MS);
}

function follow(): void {
  if (fed) return;
  fed = true;
  onEvent("orchestra_state", (f) => {
    const d = (f.data || {}) as Record<string, unknown>;
    const run = typeof d.probe_of === "string" ? d.probe_of : "";
    if (!run) return;
    set(run, { line: String(d.line || "") });
    if (d.step === "done" || d.step === "failed") void loadCoach("orchestra", run, true).then(() => set(run, { line: "" }));
  });
}

/** Follow a probe already running when the Coach tab opens (started here earlier, or by `halo coach --probe`). */
export function followProbe(run: string): void {
  follow();
  if (running(run)) poll(run);
}

/** The Probe button: the cost line first; nothing runs until the confirm. */
export async function askProbe(run: string): Promise<void> {
  set(run, { busy: "estimate", error: "" });
  try {
    const got = await api.post<{ estimate: ProbeEstimate; running: boolean }>(`${routeOf("orchestra", run)}/probe`, {});
    set(run, { estimate: got.estimate, open: true });
  } catch (e) {
    set(run, { error: msg(e) });
    toast(`Probe: ${msg(e)}`, "error", 6000);
  } finally {
    set(run, { busy: "" });
  }
}

export function cancelProbe(run: string): void {
  set(run, { open: false });
}

/** The confirm: the probe starts on a thread in Studio; its step lines follow on the card's header. */
export async function startProbe(run: string): Promise<void> {
  follow();
  set(run, { busy: "start", error: "" });
  try {
    const k = probeUi(run).estimate?.k;
    const got = await api.post<{ started: boolean; estimate: ProbeEstimate }>(`${routeOf("orchestra", run)}/probe`,
                                                                              { confirm: true, ...(k ? { k } : {}) });
    set(run, { open: false, line: `the probe started: ${got.estimate.line}` });
    toast(`Probe started on run ${run}: ${got.estimate.line}`, "info", 6000);
    await loadCoach("orchestra", run, true);
    poll(run);
  } catch (e) {
    set(run, { error: msg(e) });
    toast(`Probe: ${msg(e)}`, "error", 7000);
  } finally {
    set(run, { busy: "" });
  }
}
