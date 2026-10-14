// What each Orchestra panel and each classic canvas panel (Roles, Org,
// Design) is (`about`, one line) and how to use it (`help`, a few short
// lines). routes/help.ts merges them into HELP beside Flow's and Media's.

export type Help = { about: string; help: string };

const lines = (...l: string[]) => l.join("\n");

export const ORCHESTRA_HELP: Record<string, Help> = {
  goal: {
    about: "What you want, how it is checked and when to give up; then Run.",
    help: lines(
      "WHAT YOU WANT, DONE WHEN (what the gate checks) and STOP WHEN are required.",
      "FILES are the files the workers share; TEST is the command the gate runs.",
      "WORKERS is how many lanes (1 to 50); RETURN CAP how often a piece may go back.",
      "Run starts it; Dry run only asks the lead for the split.",
      "The top line is the open run; New run in the rail starts from a blank goal.",
    ),
  },
  graph: {
    about: "The run's plan: goal, lead, split, one node per lane, merge, test, gate.",
    help: lines(
      "Faint = not reached yet, a flowing outline = running, green = done, red = failed.",
      "The diamond is the gate: it checks DONE WHEN on the merged result.",
      "An amber arrow back means the gate returned a piece to its worker.",
      "Settings (the ... menu) labels the worker lanes with their jobs.",
    ),
  },
  grid: {
    about: "One tile per lane: writing, in review, waiting or merged.",
    help: lines(
      "The counters add the lanes up by state.",
      "A flowing tile is writing, an amber one waits, a green one is merged.",
      "Click a tile to follow that lane in Lanes and Live file.",
    ),
  },
  lanes: {
    about: "Each worker's timeline on the run's clock, from joined to merged.",
    help: lines(
      "One trace per lane, a node at each state change: hover it for its time and text.",
      "A diamond marks where the gate sent the piece back.",
      "Settings switches between elapsed time and the clock.",
    ),
  },
  file: {
    about: "The shared file, each lane's claimed part a band in its colour.",
    help: lines(
      "A band is one lane's part: claimed (hatched), writing, written or merged.",
      "It holds the lane's current text from its own worktree.",
      "Pick another file at the top when the goal has several.",
      "Settings can fold every line nobody claimed.",
    ),
  },
  report: {
    about: "The gate's verdict: every check, the finished branch, tests and cost.",
    help: lines(
      "A tick passed, a cross failed; the line says why.",
      "Copy puts the text `halo orchestra report` prints on the clipboard.",
      "A dry run shows the lead's jobs here instead.",
    ),
  },
  log: {
    about: "Every claim, merge, gate decision and note, with its time.",
    help: lines(
      "Filter by lane or by kind of line.",
      "Follow keeps the newest line in view.",
      "Settings switches between elapsed time and the clock.",
    ),
  },
  claims: {
    about: "Who holds which part of the files right now, and until when.",
    help: lines(
      "Each claim names its holder, its state and when it expires.",
      "Release frees the part; Steal gives it to the lead.",
      "A claim about to expire pulses amber.",
    ),
  },
};

export const CANVAS_HELP: Record<string, Help> = {
  "roles-canvas": {
    about: "Your lineup as cards, boxed by role: who plays each part, on which model.",
    help: lines(
      "Pick a lineup in the toolbar; drag an agent from the left list onto the canvas to add it.",
      "Drop a card into another box to change its role, onto a card to make it report there.",
      "Select a card to edit it on the right; Save writes the YAML, Apply makes it active.",
      "A lays the canvas out, F fits it, Groups shows or hides the boxes.",
    ),
  },
  "org-canvas": {
    about: "Your company in Paperclip: agents as cards, boxed by who they report to.",
    help: lines(
      "Org mode: on in the toolbar turns the company's heartbeats on.",
      "Each box holds one manager's reports; the top box is Leadership.",
      "Drop a card into a box (or onto a card) to change who it reports to.",
      "Select a card for its budget, issues and Paperclip page on the right.",
    ),
  },
  "design-canvas": {
    about: "Prototypes, pages and decks your apps make, one card per artboard.",
    help: lines(
      "Make or open a project on the left, then say what to design in Chat.",
      "Every turn saves a version; the slider under a card goes back.",
      "C pins a comment on a frame; Send comments turns the pins into a turn.",
      "Knobs move spacing and colours without a model call; Export hands it off.",
    ),
  },
};
