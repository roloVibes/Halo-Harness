// Setup's Done (3.3.3.0 R1, studio/setup_done.py): the Summary's "Done: start
// halo" posts `setup/done`; the server writes setup-done.json and publishes a
// `setup` frame {stage: "done", at}; the terminal that ran `halo init` is
// waiting for it and starts halo there. This page then leaves Setup for
// Session (its one-thing layout, nothing else opens): the door's `first`
// cleared (the rail's "set up this box" line goes, and stays gone while the
// state's `done_at` is set), `mode=setup` dropped from the address so a
// reload lands on Session too. Another open tab on Setup with `first` does
// the same when the frame reaches it.
import { api } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, goSection, studio, toast, useStore } from "../../lib/store";
import { setupDoor } from "./door";
import { setup } from "./store";

export const done = createStore<{ busy: boolean; error: string }>({ busy: false, error: "" });

export function useDoneError(): string {
  return useStore(done, (s) => s.error);
}

export function useDoneBusy(): boolean {
  return useStore(done, (s) => s.busy);
}

/** The address without `mode=setup` (the rest of the query stays): a reload opens the section saved, Session. */
function dropSetupMode(): void {
  try {
    const q = new URLSearchParams(location.search);
    if (q.get("mode") !== "setup") return;
    q.delete("mode");
    const rest = q.toString();
    history.replaceState(history.state, "", location.pathname + (rest ? `?${rest}` : "") + location.hash);
  } catch {
    /* a browser that keeps the address: the saved section still says Session */
  }
}

/** Leave Setup for Session the way Done does; `at` is the marker's time (the state's `done_at`). */
export function leaveSetup(at: string): void {
  setupDoor.update(() => ({ first: false }));
  setup.update((s) => (s.data ? { data: { ...s.data, done_at: at } } : {}));
  dropSetupMode();
  goSection("session");
}

/** POST setup/done, then leave Setup (the toast shows on Session); a refusal is the Done part's own line and the page stays. */
export async function pressDone(): Promise<boolean> {
  done.update(() => ({ busy: true, error: "" }));
  try {
    const r = await api.post<{ ok: boolean; done_at: string }>("setup/done", {});
    leaveSetup(r.done_at);
    toast("Setup is done: a halo init waiting in a terminal starts halo there", "done", 5000);
    return true;
  } catch (e) {
    done.update(() => ({ error: e instanceof Error ? e.message : String(e) })); // 3.3.5.0 R0 (h): its own line, no toast
    return false;
  } finally {
    done.update(() => ({ busy: false }));
  }
}

let fed = false;

/** Once per page: a Done pressed in another tab (its `setup` frame) moves this one too, when it is on Setup with `first`. */
export function startDoneFeed(): void {
  if (fed) return;
  fed = true;
  onEvent("setup", (frame) => {
    const d = (frame.data || {}) as { stage?: string; at?: string };
    if (d.stage !== "done" || !d.at) return;
    setup.update((s) => (s.data ? { data: { ...s.data, done_at: d.at } } : {}));
    if (studio.get().section === "setup" && setupDoor.get().first) leaveSetup(d.at);
  });
}
