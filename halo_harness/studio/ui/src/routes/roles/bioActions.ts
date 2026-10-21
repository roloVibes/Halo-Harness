// What the Bios and Models panels do (3.0.7.0 R2): open a bio into the form
// (a draft copy of its YAML mapping), edit the draft, Save it (`PUT
// bio/<name>`; a shipped bio saves as your copy, a 422 lists the validator's
// lines under the form), New / Duplicate / Delete, "Test this model" (the
// one-token probe, `POST models/test`, its result inline, never a dialog),
// the catalog's Refresh, and Analyze (3.1.9.0 R1: what each model is good at).
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { forgetResolved } from "../shared/resolve";
import { run } from "./actions";
import { clone, closeDialog, readOnlySource, roles } from "./store";
import { loadLists, loadModels, loadModelsStatus, msg, validateSoon } from "./sync";
import type { Analysis, BioPayload, Outcome, Probe, Raw } from "./types";

export async function openBio(name: string): Promise<void> {
  if (!name) return;
  roles.update(() => ({ bio: name, bioProblems: [] }));
  try {
    const b = await api.get<BioPayload>("bio/" + encodeURIComponent(name));
    if (roles.get().bio === name) roles.update(() => ({ bioData: b, bioDraft: clone(b.raw), bioProblems: [] }));
  } catch (e) {
    roles.update(() => ({ bioData: null, bioDraft: null, bioProblems: [msg(e)] }));
  }
}

/** Change the draft: `fn` edits a copy of it. */
export function editBio(fn: (raw: Raw) => void): void {
  const d = roles.get().bioDraft;
  if (!d) return;
  const next = clone(d);
  fn(next);
  roles.update(() => ({ bioDraft: next }));
}

/** `obj[key] = v`, or remove the key when v is empty (as the classic form did). */
export function setKey(obj: Raw, key: string, v: unknown): void {
  if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) delete obj[key];
  else obj[key] = v;
}

/** The mapping under `key` (made when missing). */
export function sub(obj: Raw, key: string): Raw {
  if (!obj[key] || typeof obj[key] !== "object" || Array.isArray(obj[key])) obj[key] = {};
  return obj[key] as Raw;
}

export async function saveBio(): Promise<boolean> {
  const s = roles.get();
  if (!s.bio || !s.bioDraft || !s.bioData) return false;
  const raw = clone(s.bioDraft);
  for (const k of Object.keys(raw)) {
    const v = raw[k];
    if (v && typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length) delete raw[k];
  }
  roles.update(() => ({ busy: "bio" }));
  try {
    const b = await api.put<BioPayload>("bio/" + encodeURIComponent(s.bio), { raw }, { scope: s.scope, duplicate: readOnlySource(s.bioData.scope) ? "1" : "" });
    roles.update(() => ({ bioData: b, bioDraft: clone(b.raw), bioProblems: [] }));
    toast(`${b.name} saved (${b.scope})`, "done");
    forgetResolved(); // 3.1.4.0 R4: a card's "runs on" may name this bio's model
    await loadLists();
    validateSoon(true); // the cards on this bio show its new model
    return true;
  } catch (e) {
    roles.update(() => ({ bioProblems: e instanceof ApiError && e.problems.length ? e.problems : [msg(e)] }));
    return false;
  } finally {
    roles.update(() => ({ busy: "" }));
  }
}

export async function newBio(name: string, from: string): Promise<boolean> {
  const r = await run("new-bio", () => api.post<BioPayload>("bio", { name: name.trim(), from: from || undefined }, { scope: roles.get().scope }), (b) => `${b.name} created`);
  if (!r) return false;
  closeDialog();
  await loadLists();
  await openBio(r.name);
  return true;
}

export async function deleteBio(name: string): Promise<void> {
  const r = await run("delete-bio", () => api.del("bio/" + encodeURIComponent(name), { scope: roles.get().scope }), () => `${name} deleted`);
  if (r === null) return;
  closeDialog();
  if (roles.get().bio === name) roles.update(() => ({ bio: "", bioData: null, bioDraft: null }));
  await loadLists();
  validateSoon(true);
}

/** "Test this model": a one-token round trip through the same path a session uses; the result shows inline. */
export async function testModel(ref: string): Promise<Probe | null> {
  const r = ref.trim();
  if (!r) {
    toast("Pick a model first, then Test it", "info");
    return null;
  }
  roles.update((s) => ({ probe: { ...s.probe, [r]: "running" } }));
  let got: Probe;
  try {
    got = await api.post<Probe>("models/test", { ref: r });
  } catch (e) {
    got = { ok: false, latency_ms: null, error: msg(e), cost_line: "", ref: r, reply: "" };
  }
  roles.update((s) => ({ probe: { ...s.probe, [r]: got } }));
  return got;
}

/** Refresh (3.1.4.0 R4): every provider at once, time-boxed; each one's line shows in the Models panel and under
 *  every model select (the status), a failed one as an error toast too. */
export async function refreshModels(): Promise<void> {
  const r = await run("refresh", () => api.post<{ rows: number; attempts: string[]; reason: string; outcomes?: Outcome[] }>("models/refresh", {}), (r) =>
    r.rows ? `${r.rows} models in the catalog` : r.reason || "no models found");
  if (r) (r.outcomes || []).filter((o) => !o.ok).forEach((o) => toast(`${o.name}: ${o.line}`, "error", 6000));
  roles.update(() => ({ justRefreshed: true }));
  await loadModels();
  await loadModelsStatus();
}

/** Analyze (3.1.9.0 R1): rebuild what each model is good at now (`POST models/analyze`, what `halo models analyze`
 *  does), then re-read the catalog so the picker's "best at" column follows. */
export async function analyzeModels(): Promise<void> {
  const r = await run("analyze", () => api.post<Analysis>("models/analyze", {}), (r) => `${r.rows} models analyzed`);
  if (r) roles.update(() => ({ analysis: r }));
  await loadModels();
}
