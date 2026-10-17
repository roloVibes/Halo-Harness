// What each Team panel is (`about`, one line) and how to use it (`help`, a
// few short lines), 3.0.8.0 R2; routes/help.ts merges them into HELP and the
// section help lists the `about` lines.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const TEAM_HELP: Record<string, Help> = {
  "team-board": {
    about: "The team as one board: members as columns, stages as boxes, blocks underneath.",
    help: lines(
      "Each column is a member (its lineup and role, the harness it runs on); a stage sits in the columns of its members.",
      "A stage's colour is its state: grey pending, cyan outline ready, a cyan pulse running, amber at its gate, green done, red failed, dim skipped.",
      "Edges: stage_done triggers down the right (lit once the stage they wait on is done), reads dashed and writes solid to the blocks, block_change from a block to its stage.",
      "A block's badge counts who holds a part of it (amber while someone writes); its last change is under it.",
      "Run next starts the next manual stage; Stop asks for a reason; Validate lists the file's problems and the preflight.",
    ),
  },
  "team-inspector": {
    about: "The selected stage (its row, Run, the gate card), block (holders, changes) or member.",
    help: lines(
      "Click a stage, a block or a member on the board; with nothing selected the stage at a gate shows first.",
      "Run starts that stage; a problem in the file or a blocking preflight finding is listed right here, with Run anyway for the preflight.",
      "At a gate: Accept marks it done and starts the stages after it, Redo runs it again with your instruction, Stop ends the run.",
      "A block lists who holds which part until when, and every change line (More pages back).",
      "A member's lineup opens in Roles.",
    ),
  },
  "team-feed": {
    about: "Every move of the run, newest last: states, triggers, gates, claims and changes.",
    help: lines(
      "Each line: the time since the run started, its kind, the stage, what happened.",
      "The chips hide or show a kind; report and note lines always show.",
      "Click a line to select its stage; at the bottom the list follows the live run.",
    ),
  },
};
