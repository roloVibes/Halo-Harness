// What each Design panel is (`about`) and how to use it (`help`),
// 3.0.7.0 R3: the React section that replaced the framed classic page.
// Spread into HELP (help.ts); the section help lists the `about` lines.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const DESIGN_HELP: Record<string, Help> = {
  "design-projects": {
    about: "Your design projects: pick one, or make a new one.",
    help: lines(
      "Click a project to open it in the other panels.",
      "New project asks for a name (and, if you like, its model).",
      "A project is a folder under ~/.halo/design/<slug>/.",
    ),
  },
  "design-thread": {
    about: "The project's turns: what you asked and what the model did.",
    help: lines(
      "Type what to make or change and press Enter (Shift+Enter: a new line).",
      "The reply streams in as the turn runs; Cancel turn stops it.",
      "Every turn saves a version of each artboard it changed.",
      "Send comments turns the open pins into one turn.",
    ),
  },
  "design-artboards": {
    about: "Every artboard of the project, with its versions.",
    help: lines(
      "Drag a card by its title to move it; the places are saved with the project.",
      "The slider goes back through the versions; Restore makes one the newest.",
      "Critique asks a second model for notes; Contrast checks text against its background.",
      "Rename, Delete, Download; Export and Handoff are in the toolbar.",
    ),
  },
  "design-assets": {
    about: "Files a turn can use: logos, photos, fonts, captures.",
    help: lines(
      "Add files (or drop them here) to upload them to the project's assets/.",
      "Click one to put its path in the message box.",
      "Download saves the file.",
    ),
  },
};
