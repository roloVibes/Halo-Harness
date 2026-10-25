// Feeds the Team store (3.0.8.0 R2). Once, when the section (or the status
// bar's TEAM cell) first needs it: `GET team`, then the board, the blocks and
// the run's events from line 0. Live from the `team` frames on /api/events:
// a frame's board row lands at once (the stage box moves), a gate frame's
// gate.json opens the gate card, and every frame asks for the catch-up 150 ms
// later -- `GET team/board`, `GET team/blocks` and `GET team/events?since=`
// (the feed's lines, the holders, a new run) -- so nothing is counted twice.
// While the live feed is not connected and a run is open it polls instead;
// while it is, the blocks are read again every 5 s (a claim that runs out
// sends no frame). 3.2.2.0 R6: a lineup, bio or config.json moving on disk
// (a session's edit, `halo teams apply`: `files_changed`) reads it all again.
import { api, ApiError } from "../../lib/api";
import { feedState, onEvent, type FeedFrame } from "../../lib/events";
import { onFilesChanged } from "../../lib/filesLive";
import { markActivity, setSectionStatus } from "../../lib/store";
import { runOpen, statusLine, team } from "./store";
import type { BlockStatus, BoardReply, ChangeLine, EventLine, Gate, TeamFrame, TeamInfo } from "./types";

const CATCH_MS = 150;
const POLL_MS = 2500;
const PAGE = 20;
let catchTimer = 0;
let eventsBusy = false;

export const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));
const list = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const hasTeam = () => !!team.get().info?.team;

export async function loadInfo(): Promise<void> {
  try {
    const info = await api.get<TeamInfo>("team");
    team.update(() => ({ info, loaded: true, error: "" }));
  } catch (e) {
    team.update(() => ({ loaded: true, error: msg(e) }));
  }
}

export async function loadBoard(): Promise<void> {
  if (!hasTeam()) return;
  try {
    const r = await api.get<BoardReply>("team/board");
    if (!Array.isArray(r.board?.stages)) return; // a board caught mid-write: the next catch-up reads it again
    team.update(() => ({ board: r.board, status: r.status, live: !!r.live }));
  } catch (e) {
    team.update(() => ({ error: msg(e) }));
  }
}

export async function loadBlocks(): Promise<void> {
  if (!hasTeam()) return;
  try {
    const r = await api.get<{ blocks: BlockStatus[] }>("team/blocks");
    team.update(() => ({ blocks: list<BlockStatus>(r.blocks) }));
  } catch {
    /* the board keeps the last ones */
  }
}

/** The gate lines' gate.json, by stage (the newest wins). */
function gatesOf(events: EventLine[], into: Record<string, Gate>): Record<string, Gate> {
  const out = { ...into };
  for (const e of events) {
    const g = e.kind === "gate" ? (e.data?.gate as Gate | undefined) : undefined;
    if (g && typeof g === "object" && g.stage) out[g.stage] = g;
  }
  return out;
}

export async function loadEvents(): Promise<void> {
  if (!hasTeam() || eventsBusy) return;
  eventsBusy = true;
  try {
    const s = team.get();
    const fresh = s.eventsRun !== (s.board?.run ?? null);
    const r = await api.get<{ run: string | null; events: EventLine[]; next: number }>("team/events", { since: fresh ? 0 : s.next });
    const got = list<EventLine>(r.events);
    team.update((st) => {
      const reset = fresh || st.eventsRun !== r.run;
      const events = reset ? got : [...st.events, ...got];
      return { events, next: r.next, eventsRun: r.run, gates: gatesOf(got, reset ? {} : st.gates) };
    });
  } catch {
    /* the next frame asks again */
  } finally {
    eventsBusy = false;
  }
}

/** A block's change lines from the start (or the next page with `more`). */
export async function loadChanges(block: string, more = false): Promise<void> {
  const cur = team.get().changes;
  const since = more && cur?.block === block ? cur.next : 0;
  try {
    const r = await api.get<{ block: string; changes: ChangeLine[]; next: number }>(`team/blocks/${encodeURIComponent(block)}/changes`, { since });
    const got = list<ChangeLine>(r.changes);
    team.update((s) => ({
      changes: { block, list: since && s.changes?.block === block ? [...s.changes.list, ...got] : got, next: r.next, done: got.length < PAGE, error: "" },
    }));
  } catch (e) {
    team.update(() => ({ changes: { block, list: [], next: 0, done: true, error: msg(e) } }));
  }
}

/** The board, the blocks and the new event lines: once, CATCH_MS after the last ask. */
export function catchUp(ms = CATCH_MS): void {
  window.clearTimeout(catchTimer);
  catchTimer = window.setTimeout(() => {
    void (async () => {
      await loadBoard();
      await Promise.all([loadBlocks(), loadEvents()]);
      const s = team.get();
      if (s.changes && s.sel?.kind === "block" && s.sel.id === s.changes.block) void loadChanges(s.changes.block);
    })();
  }, ms);
}

/** Everything again (after init, a reconnect or a new run). */
export async function refreshAll(): Promise<void> {
  await loadInfo();
  if (!hasTeam()) return;
  await loadBoard();
  await Promise.all([loadBlocks(), loadEvents()]);
}

function onFrame(f: FeedFrame): void {
  const d = (f.data || null) as TeamFrame | null;
  if (!d || !d.action) return;
  team.update((s) => {
    const patch: Partial<typeof s> = { frames: s.frames + 1 };
    if (d.row && s.board && s.board.run === d.run) patch.board = { ...s.board, stages: s.board.stages.map((r) => (r.id === d.row!.id ? d.row! : r)) };
    const g = d.action === "gate" ? (d.data?.gate as Gate | undefined) : undefined;
    if (g && g.stage) patch.gates = { ...s.gates, [g.stage]: g };
    return patch;
  });
  markActivity("team");
  catchUp();
}

/** Start once: the routes, the frames, the poll while the feed is down, the status line. */
export function startTeam(): void {
  if (team.get().started) return;
  team.update(() => ({ started: true }));
  void refreshAll();
  onEvent("team", onFrame);
  onFilesChanged(["lineups", "bios", "config"], () => void refreshAll());
  let ticks = 0;
  window.setInterval(() => {
    if (!runOpen(team.get())) return;
    if (feedState() !== "open") catchUp(0);
    else if (++ticks % 2 === 0) void loadBlocks(); // a claim that runs out (or a hand release) sends no frame
  }, POLL_MS);
  let last = "";
  team.subscribe(() => {
    const line = statusLine(team.get());
    if (line !== last) {
      last = line;
      setSectionStatus("team", line);
    }
  });
}
