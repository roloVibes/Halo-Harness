// What a panel is (`about`, one line) and how to use it (`help`, a few short lines), the `Help` shape every help-*.ts
// file uses; routes/help.ts merges them into HELP. 3.4.0.0 D "the runs fold": the Orchestra console's eight panels
// went with Agents' Runs view; a goal run's one panel left is the plan review on Live (routes/agents/run/planPanel.ts).

export type Help = { about: string; help: string };

const lines = (...l: string[]) => l.join("\n");

export const RUN_HELP: Record<string, Help> = {
  "orchestra-plan": {
    about: "The lead's plan before it runs: the lanes in their layers; edit them, then Approve and run.",
    help: lines(
      "Each box is a layer: the first runs at once, the next after the lanes before it.",
      "Drag a card into another box to change what it runs after; an edge shows what it takes.",
      "Click a card: its title, claims, bio, model, what it takes and hands on.",
      "Every edit is checked: a problem outlines its card in red and holds Approve and run.",
      "Reject asks for a reason and stops the run; Ctrl+Z undoes any edit.",
      "It opens from the run's lead on Live (Review the plan) and closes when the run goes on.",
    ),
  },
};
