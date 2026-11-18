// A finished goal run's report, read for its own page in the Map's drawer (3.6.0.3 B: `report:<id>`, titled "Goal run";
// History's page held it before). Read afresh each time the page opens (GET orchestra/<id>); a read that fails says why
// on the page. `back` is the page that sent him here: `run:<id>` when he pressed the run page's "Open its report" (the
// report's Back returns there), "" from every other door (Back closes the drawer).
import { api, ApiError } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import type { RunPayload } from "../../orchestra/types";

type State = { id: string; report: RunPayload | null; error: string; back: string };

export const runReport = createStore<State>({ id: "", report: null, error: "", back: "" });
export const useRunReport = <S,>(pick: (s: State) => S): S => useStore(runReport, pick);

/** Read run `id`'s report (what the page shows until it lands: "reading run <id>..."). */
export async function loadRunReport(id: string, back = ""): Promise<void> {
  runReport.update(() => ({ id, report: null, error: "", back }));
  try {
    const report = await api.get<RunPayload>(`orchestra/${encodeURIComponent(id)}`);
    if (runReport.get().id === id) runReport.update(() => ({ report }));
  } catch (e) {
    if (runReport.get().id === id) runReport.update(() => ({ error: e instanceof ApiError ? e.message : String(e) }));
  }
}
