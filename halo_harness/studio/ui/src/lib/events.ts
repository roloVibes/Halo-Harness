// The live feed: one EventSource on `/api/events?t=<token>&sessions=...`
// (the token rides in the query because EventSource cannot send headers).
// Reconnects with backoff (1 s doubling to 30 s); after five failures in a
// row the state is "down" but it keeps retrying. Subscribers register per
// event kind ("*" for all); `onFeedState` reports the connection state.
import { onTokenChange, token } from "./api";

export type FeedFrame = {
  session_id: string | null;
  /** The harness the frame came from (3.0.5.0 Fleet: the session's `fleet-id`). */
  harness?: string | null;
  event: string;
  data: Record<string, unknown> | null;
  turn: number | null;
  agent_id: string | null;
  ts: number;
};
export type FeedState = "off" | "connecting" | "open" | "retrying" | "down";
type Handler = (frame: FeedFrame) => void;

// Every kind the server forwards (studio/feed_kinds.py DEFAULT_KINDS) plus the synthesized `sessions`.
// 3.0.5.0 Fleet: agent_state (an agent-tree row changed), agent_event (a followed agent's entry), fleet.
// 3.0.7.0 R3: design_turn (a Design turn's steps). 3.0.8.0 R2: team (a team run's stage, gate, claim and change
// lines, published by Studio itself: studio/team_live.py). 3.1.1.0 R1: start (the ten-minute start's steps,
// studio/start_job.py).
export const KNOWN_KINDS = [
  "sessions", "user_message", "message_start", "message_end", "text_chunk", "tool_use_start", "tool_result",
  "tool_progress", "permission_request", "question", "plan_review", "approval_request", "todos", "status",
  "error", "turn_done", "subagent_start", "subagent_end", "subagent_queued", "subagent_progress",
  "notification", "phase", "compaction", "governor", "remote_attached",
  "orchestra_state", "orchestra_claim", "orchestra_merge", "orchestra_gate", "orchestra_report",
  "flow_state", "flow_step", "flow_gate", "flow_post", "flow_metric", "flow_report", "media_render",
  "agent_state", "agent_event", "fleet", "design_turn", "team", "start",
];

const handlers = new Map<string, Set<Handler>>();
const stateFns = new Set<(s: FeedState) => void>();
let source: EventSource | null = null;
let state: FeedState = "off";
let failures = 0;
let timer = 0;
let scope = "all";
const bound = new Set<string>();

function setState(next: FeedState): void {
  if (next === state) return;
  state = next;
  stateFns.forEach((fn) => fn(next));
}

function dispatch(kind: string, ev: MessageEvent): void {
  let frame: FeedFrame;
  try {
    frame = JSON.parse(ev.data);
  } catch {
    return;
  }
  handlers.get(kind)?.forEach((fn) => fn(frame));
  handlers.get("*")?.forEach((fn) => fn(frame));
}

function bind(kind: string): void {
  if (!source || bound.has(kind) || kind === "*") return;
  bound.add(kind);
  source.addEventListener(kind, (ev) => dispatch(kind, ev as MessageEvent));
}

function open(): void {
  window.clearTimeout(timer);
  if (!token()) {
    setState("down");
    return;
  }
  const url = `api/events?t=${encodeURIComponent(token())}&sessions=${encodeURIComponent(scope)}`;
  setState(failures ? "retrying" : "connecting");
  const es = new EventSource(url);
  source = es;
  bound.clear();
  KNOWN_KINDS.forEach(bind);
  handlers.forEach((_set, kind) => bind(kind));
  es.onopen = () => {
    failures = 0;
    setState("open");
  };
  es.onerror = () => {
    if (source !== es) return;
    es.close();
    source = null;
    failures += 1;
    setState(failures >= 5 ? "down" : "retrying");
    const wait = Math.min(30_000, 1000 * 2 ** Math.min(failures - 1, 5));
    timer = window.setTimeout(open, wait);
  };
}

/** Start (or restart) the feed. `sessions` is "all" or one session id. */
export function connectEvents(sessions = "all"): () => void {
  scope = sessions;
  disconnectEvents();
  failures = 0;
  open();
  return disconnectEvents;
}

export function disconnectEvents(): void {
  window.clearTimeout(timer);
  if (source) source.close();
  source = null;
  setState("off");
}

/** Subscribe to one kind ("*" for every frame); returns the unsubscribe. */
export function onEvent(kind: string, fn: Handler): () => void {
  let set = handlers.get(kind);
  if (!set) handlers.set(kind, (set = new Set()));
  set.add(fn);
  bind(kind);
  return () => {
    set!.delete(fn);
  };
}

export function onFeedState(fn: (s: FeedState) => void): () => void {
  stateFns.add(fn);
  fn(state);
  return () => {
    stateFns.delete(fn);
  };
}

export function feedState(): FeedState {
  return state;
}

onTokenChange(() => {
  if (state !== "off") connectEvents(scope);
});
