// Run it's one open form (3.6.0.6 P; runFlow.ts has the words): which view's form is open (`at` = "<where>:<name>",
// one at a time on the page), its task, and once Run answered, the session it started. The folder a run starts in
// is Studio's own (GET sessions/new `cwd`), read once when the first Run it is drawn, so the form's line never
// changes after it opens. A write refused for want of the proof says so in the one toast of lib/ui/Toast.tsx (with
// Make this tab yours), never a second message here.
import { api, ApiError } from "../../../lib/api";
import { isOwnerRefusal } from "../../../lib/ownerTab";
import { createStore, useStore } from "../../../lib/store";
import { openInLive } from "../../session/store";
import { RUN_PATH, canRun, runBody } from "./runWords";

export type RunForm = { at: string; name: string; text: string; busy: boolean; sid: string; error: string; folder: string };

export const runForm = createStore<RunForm>({ at: "", name: "", text: "", busy: false, sid: "", error: "", folder: "" });

export function useRunForm<S>(select: (s: RunForm) => S): S {
  return useStore(runForm, select);
}

let asked: Promise<void> | null = null;

/** Studio's folder, read once (every Run it drawn calls this; one GET per page). */
export function loadFolder(): Promise<void> {
  if (!asked) {
    asked = api.get<{ cwd?: string }>("sessions/new").then(
      (r) => runForm.update(() => ({ folder: String(r.cwd || "") })),
      () => { asked = null; });
  }
  return asked;
}

export const keyOf = (where: string, name: string): string => `${where}:${name}`;

/** Run it pressed: this view's form opens in place (another open form closes). */
export async function openRun(where: string, name: string): Promise<void> {
  await loadFolder();
  runForm.update(() => ({ at: keyOf(where, name), name, text: "", busy: false, sid: "", error: "" }));
}

export function setRunText(text: string): void {
  runForm.update(() => ({ text }));
}

export function cancelRun(): void {
  runForm.update(() => ({ at: "", sid: "", error: "", busy: false }));
}

export async function startRun(): Promise<void> {
  const s = runForm.get();
  if (!s.at || !canRun(s.text, s.busy)) return;
  runForm.update(() => ({ busy: true, error: "" }));
  try {
    const r = await api.post<{ session_id: string }>(RUN_PATH, runBody(s.name, s.text));
    runForm.update(() => ({ busy: false, sid: String(r.session_id || "") }));
  } catch (e) {
    const said = e instanceof ApiError ? e.message : String(e);
    runForm.update(() => ({ busy: false, error: isOwnerRefusal(said) ? "" : said }));
  }
}

/** Watch it in Live: Agents -> 4 · Live on the session it started (only on this press). */
export function watchRun(): void {
  const sid = runForm.get().sid;
  if (sid) openInLive(sid);
}
