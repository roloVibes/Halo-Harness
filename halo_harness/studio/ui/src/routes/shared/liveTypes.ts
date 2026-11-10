// The Live column's line (3.1.5.0 R3; liveFeed.ts keeps the list). 3.3.16.2 "thinking you can see, agents
// talking": a `thinking` line is one whole thought (`tid`, the frames' id, liveThink.ts), growing until `done`, with
// how long it took (`ms`) and its reasoning tokens when the provider reported them; a `talk` line is one agent's
// words to another (`talk`, fleet/talk.py's shape, liveTalk.ts).
import type { AgentKey } from "../fleet/types";

export type LiveKind = "text" | "thinking" | "tool" | "output" | "ask" | "spawn" | "state" | "you" | "asked" | "error" | "pack" | "talk";

/** fleet/talk.py's shape, with the speaker's and the listener's keys in this Studio. */
export type Talk = {
  id: string; from: string; to: string; why: string; re?: string; cut?: boolean; chars?: number;
  square?: string; machine?: string; fromName: string; toName: string; fromKey: AgentKey; toKey: AgentKey;
};

export type LiveLine = {
  n: number;
  key: AgentKey;
  kind: LiveKind;
  /** When it happened (unix seconds, the frame's own time). */
  ts: number;
  /** When it arrived here (ms): a running tool's clock. */
  t0: number;
  text: string;
  tool?: string;
  target?: string;
  id?: string;
  result?: string;
  /** 3.1.7.0 R1: a tool's whole result (at most FULL_MAX characters), shown when its row is clicked. */
  full?: string;
  /** When its result landed (ms); a text or a thought: its last piece. */
  ended?: number;
  error?: boolean;
  /** 3.3.10.0 R2: the packs' verdicts on the call, one line (`policy: deny -- fence: outside the project`). */
  policy?: string;
  ask?: string;
  state?: string;
  /** 3.2.0.0 R3: a pack line's KIND column (the pack's label). */
  label?: string;
  /** 3.3.0.0 R6: a steer's target name ("↳ steer to coder: ..."), and the agent's first row after it. */
  to?: string;
  after?: boolean;
  /** 3.3.16.2: a thought's id (its frames'), whether it ended, how long it took, its reasoning tokens. */
  tid?: string;
  done?: boolean;
  ms?: number;
  tokens?: number;
  /** 3.3.16.2: one agent's words to another. */
  talk?: Talk;
};
