// The Agents tab's shapes (3.6.0.0 R1): an agent/1 file (halo_harness/crew/formats.py), a row of GET crew/agents, a
// builder change line (crew/changes.py) and a Try it run's record (crew/trial.py).
export type Careful = "ask-changes" | "ask-commands" | "own";

export type More = {
  fallback?: string;
  effort?: string;
  thinking?: boolean;
  max_turns?: number;
  max_minutes?: number;
  max_usd?: number;
  reads?: string[];
  worktree?: boolean;
  offline?: boolean;
  check?: { ask: string; expect?: string };
};

export type Agent = {
  format?: string;
  name: string;
  does: string;
  instructions?: string;
  model: string;
  needs?: string[];
  uses: string[];
  careful: Careful;
  more?: More;
};

export type Scope = "yours" | "project" | "starter";

export type Row = Agent & { scope: Scope; new: boolean; used: string[]; problems: string[] };

export type Change = {
  id: string;
  kind: "create" | "change" | "remove" | "fill";
  target: string;
  summary: string;
  widen: boolean;
  ticked: boolean;
  fill?: { field: string; value: string };
};

export type Question = { text: string; choices: string[] };

export type Meta = { model: string; model_from: string; typical: string; spent_usd: number; cap_usd: number; reached: boolean };

export type Msg = { me?: boolean; text: string; question?: Question; cost?: number };

export type TryRec = {
  id: string;
  agent: string;
  model: string;
  model_line: string;
  request: string;
  state: "running" | "stopping" | "done" | "stopped" | "failed";
  where: string;
  reply: string;
  used: Record<string, number>;
  denied: string[];
  cost_usd: number | null;
  turns: number | null;
  seconds: number | null;
  now: string;
  seen: boolean;
  error: string;
  estimate: { usd: number | null; line: string };
};

export const USES: [string, string, string, string][] = [
  ["read", "Read files", "can open any file in the project", "it cannot see your files"],
  ["edit", "Change files", "can write and delete files in the project (git can undo it)", "it can read but never change files"],
  ["bash", "Run commands", "can run shell commands: tests, builds, git", "it cannot run anything"],
  ["web", "The web", "can search and open web pages", "it stays off the web"],
];

export const CAREFUL: [Careful, string, string][] = [
  ["ask-changes", "Asks before it changes anything", "every edit and every command waits for your OK"],
  ["ask-commands", "Changes files on its own, asks before commands", "edits go ahead; a command waits for your OK"],
  ["own", "Works on its own", "nothing waits for you; your deny rules still hold"],
];

export const blank = (name: string): Agent => ({ format: "agent/1", name, does: "", model: "auto", uses: ["read"], careful: "ask-changes", more: {} });
