// Wires the live feed (lib/events) into the shell's store: connection state,
// the attached sessions, an event counter, per-section activity, and the
// last 100 frames for the Orchestra feed panel. `?feed=off` keeps it shut
// (headless captures).
import { connectEvents, onEvent, onFeedState, type FeedFrame } from "../lib/events";
import { createStore, studio, type SessionInfo } from "../lib/store";

export const recent = createStore<{ frames: FeedFrame[] }>({ frames: [] });
let started = false;

export function startFeed(): void {
  if (started) return;
  started = true;
  onFeedState((status) => studio.update((s) => ({ feed: { ...s.feed, status } })));
  onEvent("sessions", (f) => {
    const rows = Array.isArray(f.data?.sessions) ? (f.data!.sessions as SessionInfo[]) : [];
    studio.update((s) => ({ feed: { ...s.feed, sessions: rows } }));
  });
  onEvent("*", (f) => {
    if (f.event === "sessions") return;
    const now = Date.now();
    studio.update((s) => ({
      feed: { ...s.feed, events: s.feed.events + 1, lastKind: f.event, lastTs: now },
      activity: { ...s.activity, orchestra: now },
    }));
    recent.update((r) => ({ frames: [...r.frames.slice(-99), f] }));
  });
  if (!/[?&]feed=off\b/.test(location.search)) connectEvents("all");
}
