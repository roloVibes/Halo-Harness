// How long Studio waits for one request (3.6.0.2 P4 batch 9): a read that never ends must not leave a door closed for
// good, so every request has a time limit -- 30 s -- and a request that hits it fails like any other failed read (the
// words the page already shows for one: "Studio server unreachable: ..."). A longer limit only for the routes named
// here, each because its answer waits on a model, another machine, a download or a run starting; no retry is added.
// Pure: node-tested (tests/test_api_limit.py).

export const LIMIT_MS = 30_000;
export const LONG_MS = 15 * 60_000;

/** [a route's path, why it may take longer than 30 s] */
export const LONG: [RegExp, string][] = [
  [/^builder$/, "the builder asks a model"],
  [/^local\/steward\/chat$/, "the steward asks a model"],
  [/^local\/voice\b/, "speech in and out runs a model"],
  [/^local\/advise$/, "the advice reads every host"],
  [/^local\/host\/[^/]+\/(bench|probe|pull|tune|dialect)\b/, "a host loads, pulls or measures a model"],
  [/^local\/pool\/(bench|run|scan|warm|preflight|recommend)$/, "the pool measures or loads models on its hosts"],
  [/^local\/hf\/(download|serve)$/, "a download, or a model server starting"],
  [/^local\/(library\/(refresh|verify|verifies)|shelf\/repull|warm-set|refresh)$/, "a catalogue read or a model pulled again"],
  [/^models\/(test|analyze|check|think|refresh|best-for)$/, "the answer asks a model"],
  [/^setup\/(check|copilot|ollama)\b/, "setup reaches a provider or a host"],
  [/^crew\/(try|estimate)$/, "a Try it run starts, or a workflow is costed by a model"],
  [/^live\/report$/, "a run's report card reads its whole record"],
  [/^sessions\/[^/]+\/(postmortem|eyes|command|slash)$/, "a session's command or a model's look at it"],
  [/^sessions\/new$/, "a session's terminal starting"],
  [/^orchestra\/run$/, "a goal run starting (its worktrees)"],
  [/^live\/[^/]+\/[^/]+\/(recording|agents\/[^/]+\/handoff)$/, "a recording written, or a hand-off's brief"],
  [/^media\//, "media work runs a model"],
  [/^gym$/, "the gym runs a model"],
  [/^packs?\//, "a pack's own route or its update: Studio cannot know how long it takes"],
];

/** The time limit of a request to `path` (no leading slash, no query). */
export function limitFor(path: string): number {
  const p = path.replace(/^\/+/, "").replace(/^api\//, "").split("?")[0];
  return LONG.some(([re]) => re.test(p)) ? LONG_MS : LIMIT_MS;
}

/** The error a request that hit its limit fails with (its message follows the page's "Studio server unreachable: "). */
export const overLimit = (ms: number): Error => new Error(`no answer in ${Math.round(ms / 1000)} s`);

/** 3.6.0.14 O1-6: the error a read its caller dropped fails with (the step-in sheet closed first): quiet, never a stop. */
export const DROPPED = new Error("dropped by its caller");

/** `go(signal)` (a fetch), given up after `ms`: rejects with `overLimit(ms)` and aborts the request; `outer`, the caller's
 *  own signal: when it aborts, the request is aborted at once and rejects with DROPPED. */
export function within<T>(go: (signal: AbortSignal) => Promise<T>, ms: number, outer?: AbortSignal): Promise<T> {
  const ctl = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined, off = () => {};
  const late = new Promise<never>((_, no) => {
    timer = setTimeout(() => (ctl.abort(), no(overLimit(ms))), ms);
    const drop = () => (ctl.abort(), no(DROPPED));
    if (outer?.aborted) drop();
    else if (outer) (outer.addEventListener("abort", drop, { once: true }), (off = () => outer.removeEventListener("abort", drop)));
  });
  return Promise.race([go(ctl.signal), late]).finally(() => (clearTimeout(timer), off()));
}
