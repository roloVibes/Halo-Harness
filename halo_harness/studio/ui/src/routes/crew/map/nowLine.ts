// NOW in words (3.6.0.13 L1, R11): what a helper (or main) does now, on Agents -> Live and Session's drawing. The FIRST
// branch that applies, built from the word functions that already exist (never a second copy of a word):
//   waiting -> "waiting for you · {s}"; paused -> "paused"; queued -> "queued · {s}" (from the row's since);
//   stopped / done / failed -> "stopped after {span}" / "done in {span}" / "failed after {span}" -- the blank kept line
//   when Studio never saw the end (the end or the start is 0: the state line already says it);
//   an open tool -> "{tool} · {s}" (its raw name, as the Feed draws it); a tool only the row knows -> "{tool}" alone;
//   the newest line a thought -> "thinking · {s}"; writing -> "writing · {s}" (from the newest text line);
//   else "waiting for a model reply · {s}" (from the wait's own since); nothing known -> "" (the blank kept line).
// A line whose seconds are unknown never ends in a separator: its words stand alone. No talk branch (TALK is out).
// Pure: no React, no DOM, no store, no clock of its own (tests/test_map_groups.py runs it in node).
import { secsWords, type Wait } from "../live/waits";
import { span } from "./groupWords";
import { waitWhat } from "./truth";
import { toolClock, waitClock } from "./truthBits";

/** `kind` tells the colour (live-now.css): "think" a thought, "wait" waiting on you, "tool" a tool, else "". */
export type NowKind = "tool" | "think" | "wait" | "";
/** `text`: the words before the seconds; `secs`: the seconds, drawn in the 10ch slot `.mp-clock-secs`. */
export type Now = { text: string; secs: string; kind: NowKind };
/** The row's raw state and since/end (seconds; 0 unknown), the feed's open tool and newest line (ms), its wait. */
export type NowIn = { raw: string; started: number; ended: number; tool?: { tool: string; t0: number } | null;
  last?: { kind: string; t0: number; ended?: number } | null; wait?: Wait | null };

export const NO_NOW: Now = { text: "", secs: "", kind: "" };
const SEP_END = / · $/;
/** "{word} · {s}": a state that counts (queued, thinking, writing) in the tool clock's shape. */
const counting = (word: string): string => toolClock(word, "");

export function nowOf(x: NowIn, nowMs: number): Now {
  const w = x.wait || null;
  const at = (words: string, t0: number | null, kind: NowKind = ""): Now => {
    const secs = secsWords(t0, nowMs);
    return secs ? { text: words, secs, kind } : { text: words.replace(SEP_END, ""), secs: "", kind };
  };
  const ran = (words: string): Now => (x.started > 0 && x.ended > 0 ? { text: `${words} ${span(x.ended - x.started)}`, secs: "", kind: "" } : NO_NOW);
  switch (x.raw) {
    case "waiting": return at(waitClock(waitWhat("you"), ""), w?.since ?? null, "wait");
    case "paused": return { text: "paused", secs: "", kind: "" };
    case "queued": return at(counting("queued"), x.started > 0 ? x.started * 1000 : null);
    case "stopped": return ran("stopped after");
    case "done": return ran("done in");
    case "failed": return ran("failed after");
  }
  if (x.tool) return at(toolClock(x.tool.tool, ""), x.tool.t0, "tool");
  if (w?.tool && (w.kind === "tool" || w.kind === "agent")) return at(toolClock(w.tool, ""), w.since, "tool");
  if (x.last?.kind === "thinking") return at(counting("thinking"), x.last.t0, "think");
  if (w?.kind === "nothing" && x.last?.kind === "text") return at(counting("writing"), x.last.t0);
  if (w?.kind === "model") return at(waitClock(waitWhat("model"), ""), w.since);
  return NO_NOW;
}

/** NOW's whole words (the hover's "Now: ..."). */
export const nowWords = (n: Now): string => n.text + n.secs;
