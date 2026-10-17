// What the Design panels added in 3.0.7.0 R3b say about themselves (spread
// over routes/help-org-design.ts's lines in Design.tsx): the design-system
// panel, and Artboards and Thread with the knobs, the direct text edits,
// pinning a comment, the device select and "3 directions".
import type { Help } from "../help-orchestra";

const lines = (...l: string[]) => l.join("\n");

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
};
