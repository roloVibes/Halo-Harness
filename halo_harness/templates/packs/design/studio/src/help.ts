// What the Design panels added in 3.0.7.0 R3b say about themselves (spread over help-panels.ts's lines in
// Design.tsx): the design-system panel, and Artboards and Thread with the knobs, the direct text edits, pinning a
// comment, the device select and "3 directions". 3.3.13.0 R2: and the section's own copy (the Start view's "what"
// and steps), which was the core's routes/sectionHelp.ts `design` before the design pack.
export type Help = { about: string; help: string };

const lines = (...l: string[]) => l.join("\n");

export const SECTION_COPY = {
  what: "Prototypes, pages, decks and logos made by your own apps and models. A project is a folder of artboards in the design pack's data folder, and every turn saves a new version.",
  steps: [
    ["Make or open a project", "The Start view names the first one; then Projects lists them all, and New project makes another."],
    ["Say what to design", "Write it in Thread and press Enter: the reply streams in as the turn works; Cancel turn stops it."],
    ["Look and compare", "Artboards: drag a card by its title (the places are saved with the project), slide back through its versions, Restore one."],
    ["Pin comments, ask for notes", "Pick Comment and click a frame to pin a note; Critique has a second model pin its own; Contrast checks text against its background; Send comments turns the pins into a turn."],
    ["Change it by hand", "Double-click a text in a prototype to edit it in place; a card's Knobs; the Design system panel's tokens and Sync; Rename, Delete or Download an artboard."],
    ["Hand it off", "Export writes a folder, HTML, PNG, SVG or PDF; Handoff bundles it for the next Halo or Claude Code session."],
    ["Use your own files", "Assets: add or drop logos and photos; click one to put its path in the message."],
    ["Render pictures", "Render queues a ComfyUI workflow into an artboard of the project (halo media points Halo at ComfyUI)."],
  ] as [string, string][],
};

export const DESIGN_MORE_HELP: Record<string, Help> = {
  "design-artboards": {
    about: "Every artboard of the project, with its versions, pins and knobs.",
    help: lines(
      "Drag a card by its title; double-click a text in a prototype to edit it (Enter saves a new version, Esc cancels).",
      "Comment, then click a frame, pins a comment there; click a pin for its text and Resolve.",
      "The device select draws prototypes at phone, tablet or desktop size; Settings keeps it.",
      "Knobs (on the card, or Settings) change spacing and colours at once, each a new version.",
      "The slider goes back through versions; Restore, Critique, Contrast, Rename, Delete, Export and Handoff.",
    ),
  },
  "design-thread": {
    about: "The project's turns: what you asked and what the model did.",
    help: lines(
      "Type what to make or change and press Enter (Shift+Enter: a new line).",
      "3 directions sends it as three different artboards, named after the box beside it.",
      "The reply streams in as the turn runs; Cancel turn stops it.",
      "Send comments turns the open pins into one turn.",
    ),
  },
  "design-system": {
    about: "The project's design system: the tokens every turn designs with.",
    help: lines(
      "Tokens by group (colours, type, spacing, radii); a colour shows its swatch.",
      "Edit a value and press Save tokens; the next turn uses it.",
      "Sync reads tokens from a codebase folder or a web page, then says what it found.",
    ),
  },
  "design-render": {
    about: "A ComfyUI workflow rendered into an artboard of this project.",
    help: lines(
      "Pick a workflow (a starter, or one saved on ComfyUI), fill its inputs, name the artboard and press Render.",
      "The render runs on the ComfyUI Halo is pointed at (halo media init); its steps show here as it goes.",
      "Each output becomes an artboard (or the artboard's next version): it shows in Artboards.",
    ),
  },
  "design-settings": {
    about: "The design pack's settings: the model a new project starts with, a turn's spending cap.",
    help: lines("Each field is a key of the pack's config.schema; Save checks it and writes packs.settings.design."),
  },
};
