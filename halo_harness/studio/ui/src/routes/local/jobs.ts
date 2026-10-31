// Local's pull jobs (3.3.5.0 R3; studio/local_pull_job.py, studio/local_control_api.py): GET local/pulls for a page
// that opens while one runs, then every `pull` frame; POST local/host/<host>/pull {name} starts one (a second ask for
// the same name joins it), POST local/pull/<id>/cancel stops it. A pull is the server's job: it goes on when the page
// closes. When one ends well, the Library, Models and Hosts pages read again (the Library row says "installed on").
// 3.3.5.0 R5: a Hugging Face download is a job of kind "download" in the same list (`download` frames; POST
// local/hf/download starts one, POST local/download/<id>/cancel stops it): its end reads the model folders again.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { loadDirs } from "./hfstore";
import { loadLibrary } from "./libstore";
import { loadHosts, loadModels } from "./store";
import type { PullJob } from "./types";

type Jobs = { jobs: Record<string, PullJob>; said: Record<string, string> };
export const jobs = createStore<Jobs>({ jobs: {}, said: {} });

export function useJobs<S>(select: (s: Jobs) => S): S {
  return useStore(jobs, select);
}

export const jobKey = (host: string, name: string) => `${host}|${name}`;
export const pullLine = (name: string, host: string) => `halo models pull ${name} --host ${host}`;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export function takeJob(j: PullJob): void {
  const before = jobs.get().jobs[j.job];
  jobs.update((s) => ({ jobs: { ...s.jobs, [j.job]: { ...(s.jobs[j.job] || {}), ...j } } }));
  if (j.done && j.ok && !(before && before.done)) {
    void loadLibrary();
    if (j.kind === "download") {
      void loadDirs();
    } else {
      void loadModels();
      void loadHosts();
    }
  }
}

const take = takeJob;

/** The newest job for this host and name (running first). */
export function jobFor(s: Jobs, host: string, name: string): PullJob | undefined {
  const all = Object.values(s.jobs).filter((j) => j.host === host && j.name === name);
  return all.find((j) => !j.done) || all.sort((a, b) => b.started - a.started)[0];
}

/** The newest download job for this repo and file (running first). */
export function dlJobFor(s: Jobs, repo: string, file: string): PullJob | undefined {
  const all = Object.values(s.jobs).filter((j) => j.kind === "download" && j.repo === repo && (j.file || "") === (file || ""));
  return all.find((j) => !j.done) || all.sort((a, b) => b.started - a.started)[0];
}

export async function loadPulls(): Promise<void> {
  try {
    const r = await api.get<{ jobs: PullJob[] }>("local/pulls");
    for (const j of r.jobs || []) take(j);
  } catch {
    /* the frames fill it in */
  }
}

export async function startPull(host: string, name: string): Promise<void> {
  const k = jobKey(host, name);
  jobs.update((s) => ({ said: { ...s.said, [k]: "" } }));
  try {
    const j = await api.post<PullJob>(`local/host/${encodeURIComponent(host)}/pull`, { name });
    take(j);
  } catch (e) {
    jobs.update((s) => ({ said: { ...s.said, [k]: msg(e) } }));
  }
}

export async function cancelPull(id: string, kind?: string): Promise<void> {
  try {
    const j = await api.post<PullJob>(`local/${kind === "download" ? "download" : "pull"}/${encodeURIComponent(id)}/cancel`, {});
    take(j);
  } catch {
    /* the job's next frame says where it is */
  }
}

let live = false;

/** Once: the `pull` frames, and the jobs already running. */
export function startJobs(): void {
  if (live) return;
  live = true;
  for (const kind of ["pull", "download"]) {
    onEvent(kind, (f) => {
      const j = f.data as PullJob | undefined;
      if (j && j.job) take(j);
    });
  }
  void loadPulls();
}

export function rate(n: number | null | undefined): string {
  if (typeof n !== "number" || n <= 0) return "";
  return n >= 1e6 ? `${(n / 1e6).toFixed(0)} MB/s` : `${Math.round(n / 1e3)} KB/s`;
}

export function eta(s: number | null | undefined): string {
  if (typeof s !== "number") return "";
  return s < 90 ? `${s} s left` : s < 5400 ? `${Math.round(s / 60)} min left` : `${(s / 3600).toFixed(1)} h left`;
}
