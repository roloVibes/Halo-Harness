// What the model picker's buttons do (3.6.0.0 R5, from the Roles bio actions): "Test this model" (the one-token probe,
// `POST models/test`, its result inline, never a dialog), the catalog's Refresh, and Analyze (3.1.9.0 R1: what each model
// is good at). `run` marks the action busy while it runs and says how it went.
import { api } from "../../../lib/api";
import { toast } from "../../../lib/store";
import { models } from "./store";
import { loadModels, loadModelsStatus, msg } from "./sync";
import type { Analysis, Outcome, Probe } from "./types";

export async function run<T>(busy: string, fn: () => Promise<T>, done?: (r: T) => string): Promise<T | null> {
  models.update(() => ({ busy }));
  try {
    const r = await fn();
    if (done) toast(done(r), "done");
    return r;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return null;
  } finally {
    models.update(() => ({ busy: "" }));
  }
}

/** "Test this model": a one-token round trip through the same path a session uses; the result shows inline. */
export async function testModel(ref: string): Promise<Probe | null> {
  const r = ref.trim();
  if (!r) {
    toast("Pick a model first, then Test it", "info");
    return null;
  }
  models.update((s) => ({ probe: { ...s.probe, [r]: "running" } }));
  let got: Probe;
  try {
    got = await api.post<Probe>("models/test", { ref: r });
  } catch (e) {
    got = { ok: false, latency_ms: null, error: msg(e), cost_line: "", ref: r, reply: "" };
  }
  models.update((s) => ({ probe: { ...s.probe, [r]: got } }));
  return got;
}

/** Refresh (3.1.4.0 R4): every provider at once, time-boxed; each one's line shows under every model select (the
 *  status), a failed one as an error toast too. */
export async function refreshModels(): Promise<void> {
  const r = await run("refresh", () => api.post<{ rows: number; attempts: string[]; reason: string; outcomes?: Outcome[] }>("models/refresh", {}), (r) =>
    r.rows ? `${r.rows} models in the catalog` : r.reason || "no models found");
  if (r) (r.outcomes || []).filter((o) => !o.ok).forEach((o) => toast(`${o.name}: ${o.line}`, "error", 6000));
  models.update(() => ({ justRefreshed: true }));
  await loadModels();
  await loadModelsStatus();
}

/** Analyze (3.1.9.0 R1): rebuild what each model is good at now (`POST models/analyze`, what `halo models analyze`
 *  does), then re-read the catalog so the picker's "best at" column follows. */
export async function analyzeModels(): Promise<void> {
  const r = await run("analyze", () => api.post<Analysis>("models/analyze", {}), (r) => `${r.rows} models analyzed`);
  if (r) models.update(() => ({ analysis: r }));
  await loadModels();
}
