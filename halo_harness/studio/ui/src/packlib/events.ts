// api.lib.events (3.3.13.0 R2, extension API 1.2): the live feed the shell is already connected to. `on(kind, fn)`
// subscribes (returns the function that stops it; "*" for every kind), `state()` / `onState(fn)` the connection.
// A pack's own frames come as `pack_event` (published, kept in its events log) and `pack_live` (its routes'
// ctx.publish: live only); the bundle api's `on(kind, cb)` already filters both to the pack's own.
import { feedState, onEvent, onFeedState, type FeedFrame, type FeedState } from "../lib/events";

export { feedState, onEvent, onFeedState, type FeedFrame, type FeedState };
export const on = onEvent;
export const state = feedState;
export const onState = onFeedState;
