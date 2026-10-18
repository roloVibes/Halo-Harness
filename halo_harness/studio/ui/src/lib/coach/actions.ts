// The coach loop's actions (3.1.3.0 R1), shared by every report face: Ask the
// model (POST <route>/ask: the run's lead's paragraph for one card, kept with
// the run), Apply (POST <route>/apply: first the confirm card -- the file and
// the before -> after diff, nothing written -- then, confirmed, the write) and
// Undo (POST <route>/undo: the file put back when it still holds what Apply
// wrote). Each answer lands on the card in the coach store; the card's busy
// word and the open confirm card live here too.
import { api, ApiError } from "../api";
import { toast } from "../store";
import { coach, keyOf, loadCoach, routeOf } from "./store";
import type { CoachAsk, CoachPreview, CoachRunKind, Suggestion } from "./types";

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const cardKey = (kind: CoachRunKind, run: string, id: string) => `${keyOf(kind, run)}:${id}`;
const query = (kind: CoachRunKind, run: string) => (kind === "team" ? { run } : undefined);

function setBusy(key: string, word: string): void {
  coach.update((s) => ({ busy: { ...s.busy, [key]: word } }));
}

function patch(kind: CoachRunKind, run: string, id: string, fields: Partial<Suggestion>): void {
  const key = keyOf(kind, run);
  coach.update((s) => {
    const entry = s.runs[key];
    if (!entry?.result) return {};
    const suggestions = entry.result.suggestions.map((x) => (x.id === id ? { ...x, ...fields } : x));
    return { runs: { ...s.runs, [key]: { ...entry, result: { ...entry.result, suggestions } } } };
  });
}

export const busyOf = (kind: CoachRunKind, run: string, id: string) => coach.get().busy[cardKey(kind, run, id)] || "";
export { cardKey };

/** The run's lead explains one card in a paragraph (kept with the run; `refresh` asks again). */
export async function askModel(kind: CoachRunKind, run: string, id: string, refresh = false): Promise<void> {
  const key = cardKey(kind, run, id);
  setBusy(key, "ask");
  try {
    const got = await api.post<CoachAsk>(`${routeOf(kind, run)}/ask`, { id, refresh }, query(kind, run));
    patch(kind, run, id, { paragraph: got.paragraph || null, paragraph_error: got.error || "" });
  } catch (e) {
    patch(kind, run, id, { paragraph_error: msg(e) });
  } finally {
    setBusy(key, "");
  }
}

/** Apply, step one: the confirm card (what file, the diff). Nothing is written. */
export async function previewApply(kind: CoachRunKind, run: string, id: string): Promise<void> {
  const key = cardKey(kind, run, id);
  setBusy(key, "preview");
  try {
    const got = await api.post<{ preview: CoachPreview }>(`${routeOf(kind, run)}/apply`, { id }, query(kind, run));
    coach.update((s) => ({ confirm: { ...s.confirm, [key]: got.preview } }));
  } catch (e) {
    toast(`Apply ${id}: ${msg(e)}`, "error", 6000);
  } finally {
    setBusy(key, "");
  }
}

export function cancelApply(kind: CoachRunKind, run: string, id: string): void {
  const key = cardKey(kind, run, id);
  coach.update((s) => {
    const { [key]: _gone, ...rest } = s.confirm;
    return { confirm: rest };
  });
}

/** Apply, step two: write the change the confirm card showed, then read the card again (it shows Applied). */
export async function confirmApply(kind: CoachRunKind, run: string, id: string): Promise<void> {
  const key = cardKey(kind, run, id);
  setBusy(key, "apply");
  try {
    const got = await api.post<{ applied: { apply_id: string; file: string } }>(
      `${routeOf(kind, run)}/apply`, { id, confirm: true }, query(kind, run));
    cancelApply(kind, run, id);
    toast(`Applied ${got.applied.apply_id}: ${got.applied.file}. Undo puts it back.`, "done", 6000);
    await loadCoach(kind, run, true);
  } catch (e) {
    toast(`Apply ${id}: ${msg(e)}`, "error", 6000);
  } finally {
    setBusy(key, "");
  }
}

/** Undo an apply: the file goes back to its text from before, if it still holds what Apply wrote. */
export async function undoApply(kind: CoachRunKind, run: string, id: string, applyId: string): Promise<void> {
  const key = cardKey(kind, run, id);
  setBusy(key, "undo");
  try {
    const got = await api.post<{ message: string }>(`${routeOf(kind, run)}/undo`, { apply_id: applyId }, query(kind, run));
    toast(got.message, "done", 6000);
    await loadCoach(kind, run, true);
  } catch (e) {
    toast(`Undo ${applyId}: ${msg(e)}`, "error", 7000);
  } finally {
    setBusy(key, "");
  }
}
