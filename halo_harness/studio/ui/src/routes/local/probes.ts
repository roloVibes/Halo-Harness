// Local's probe jobs (3.3.6.0 R1; studio/local_probe_job.py, studio/local_probe_api.py): the battery on one model.
// POST local/host/<host>/probe {model, force?} starts one (a second ask joins it) and answers with the cost line;
// every `probe` frame moves its progress strip; GET local/probes catches up a page that opens while one runs. When
// one ends well the Models rows read again (the card's four blocks, the chips and the "probed <date>" mark).
// A twin's verify result arrives as a `twin-verify` frame: the rows read again too.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { loadModels } from "./store";

export type ProbeJob = {
  job: string; host: string; model: string; step: number; of: number; probe: string; say: string; done: boolean;
  ok: boolean; error: string | null; started: number; via: string; cost: string; remote?: boolean;
};
type Probes = { jobs: Record<string, ProbeJob>; said: Record<string, string> };
export const probes = createStore<Probes>({ jobs: {}, said: {} });

export function useProbes<S>(select: (s: Probes) => S): S {
  return useStore(probes, select);
}

export const probeKey = (host: string, model: string) => `${host}|${model}`;
export const probeLine = (model: string, host: string, force = false) => `halo models probe ${model} --host ${host}${force ? " --force" : ""}`;
export const costLine = (model: string, host: string) => `about 8 requests to ${model} on ${host}, 1-3 minutes, no cost; it loads the model`;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

function take(j: ProbeJob): void {
  const before = probes.get().jobs[j.job];
  probes.update((s) => ({ jobs: { ...s.jobs, [j.job]: { ...(s.jobs[j.job] || {}), ...j } } }));
  if (j.done && j.ok && !(before && before.done)) void loadModels();
}

/** The newest probe job for this host and model (running first). */
export function probeFor(s: Probes, host: string, model: string): ProbeJob | undefined {
  const all = Object.values(s.jobs).filter((j) => j.host === host && j.model === model);
  return all.find((j) => !j.done) || all.sort((a, b) => b.started - a.started)[0];
}

export async function startProbe(host: string, model: string, force: boolean): Promise<void> {
  const k = probeKey(host, model);
  probes.update((s) => ({ said: { ...s.said, [k]: "" } }));
  try {
    take(await api.post<ProbeJob>(`local/host/${encodeURIComponent(host)}/probe`, { model, force }));
  } catch (e) {
    probes.update((s) => ({ said: { ...s.said, [k]: msg(e) } }));
  }
}

let live = false;

/** Once: the `probe` and `twin-verify` frames, and the probe jobs already running. */
export function startProbes(): void {
  if (live) return;
  live = true;
  onEvent("probe", (f) => {
    const j = f.data as ProbeJob | undefined;
    if (j && j.job) take(j);
  });
  onEvent("twin-verify", () => {
    void loadModels();
  });
  void api.get<{ jobs: ProbeJob[] }>("local/probes").then((r) => {
    for (const j of r.jobs || []) take(j);
  }, () => {
    /* the frames fill it in */
  });
}
