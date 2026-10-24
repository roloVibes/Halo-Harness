// Wires the live feed (lib/events) into the shell's store: connection state,
// the attached sessions, an event counter, per-section activity (agent_* and
// fleet frames count for Fleet, design_turn frames for Design), and the
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
    if (f.event === "sessions" || f.event === "start" || f.event === "focus") return; // start: its own dialog; focus: lib/edit.ts
    if (f.event === "pack_changed" || f.event === "pack_event") return; // 3.2.0.0 R3: routes/packs/store.ts reads them
    const now = Date.now();
    const section = /^media_/.test(f.event) || f.event === "design_turn" ? "design" : /^(agent_|fleet$)/.test(f.event) ? "fleet" : "orchestra";
    studio.update((s) => ({
      feed: { ...s.feed, events: s.feed.events + 1, lastKind: f.event, lastTs: now },
      activity: { ...s.activity, [section]: now },
    }));
    recent.update((r) => ({ frames: [...r.frames.slice(-99), f] }));
  });
  if (!/[?&]feed=off\b/.test(location.search)) connectEvents("all");
}
