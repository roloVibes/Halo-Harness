// Download and verify, the role offer and Save as role template (3.3.6.0 R2; studio/local_search_api.py,
// studio/local_verify_job.py): POST local/library/verify {host, name, role} starts one job -- the pull (its `pull`
// frames feed jobs.ts's bar), the battery (`probe` frames, probes.ts), then the offer -- and every `verify` frame
// moves its stage here; GET local/library/verifies catches up a page that opens while one runs. Assign posts the
// offer (POST local/library/assign: the lineup's role gets the model); Save as role template posts the preset's
// bundle as it stands (POST local/library/template).
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { loadLibrary } from "./libstore";
import type { VerifyJob } from "./types";

type Verify = { jobs: Record<string, VerifyJob>; said: Record<string, { ok: boolean; text: string }> };
export const verify = createStore<Verify>({ jobs: {}, said: {} });

export function useVerify<S>(select: (s: Verify) => S): S {
  return useStore(verify, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const say = (k: string, ok: boolean, text: string) => verify.update((s) => ({ said: { ...s.said, [k]: { ok, text } } }));

function take(j: VerifyJob): void {
  const before = verify.get().jobs[j.job];
  verify.update((s) => ({ jobs: { ...s.jobs, [j.job]: { ...(s.jobs[j.job] || {}), ...j } } }));
  if (j.done && !(before && before.done)) void loadLibrary();
}

/** The newest verify job for this host and name (running first). */
export function verifyFor(s: Verify, host: string, name: string): VerifyJob | undefined {
  const all = Object.values(s.jobs).filter((j) => j.host === host && j.name === name);
  return all.find((j) => !j.done) || all.sort((a, b) => b.started - a.started)[0];
}

export async function startVerify(host: string, name: string, role: string): Promise<void> {
  const k = `v|${host}|${name}`;
  say(k, true, "");
  try {
    take(await api.post<VerifyJob>("local/library/verify", { host, name, role }));
  } catch (e) {
    say(k, false, msg(e));
  }
}

export async function assignRole(job: VerifyJob): Promise<void> {
  if (!job.offer) return;
  try {
    const r = await api.post<{ ok: boolean; say: string }>("local/library/assign", { role: job.offer.role, ref: job.offer.ref });
    say(`a|${job.job}`, r.ok, r.say);
  } catch (e) {
    say(`a|${job.job}`, false, msg(e));
  }
}

export async function saveTemplate(preset: string, bundle: Record<string, unknown>, model = ""): Promise<void> {
  try {
    const r = await api.post<{ ok: boolean; say: string }>("local/library/template", { preset, bundle, model });
    say(`t|${preset}`, r.ok, r.say);
  } catch (e) {
    say(`t|${preset}`, false, msg(e));
  }
}

let live = false;

/** Once: the `verify` frames, and the jobs already running. */
export function startVerifies(): void {
  if (live) return;
  live = true;
  onEvent("verify", (f) => {
    const j = f.data as VerifyJob | undefined;
    if (j && j.job) take(j);
  });
  void api.get<{ jobs: VerifyJob[] }>("local/library/verifies").then((r) => {
    for (const j of r.jobs || []) take(j);
  }, () => {
    /* the frames fill it in */
  });
}
