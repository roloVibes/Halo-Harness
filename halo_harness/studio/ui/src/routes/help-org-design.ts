// What each Org and Design panel is (`about`) and how to use it (`help`),
// 3.0.7.0 R3: the React sections that replace the framed classic pages.
// Spread into HELP (help.ts); the section help lists the `about` lines.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const ORG_HELP: Record<string, Help> = {
  "org-company": {
    about: "Paperclip here: installed, running, which company, and Org mode.",
    help: lines(
      "The dots say whether Paperclip is installed, running and linked to a company.",
      "Org mode on lets the company's agents run on their heartbeats; off pauses them.",
      "Sync puts a lineup's agents into the company; Pull writes its reporting lines back.",
      "Link picks the company Studio shows.",
    ),
  },
  "org-chart": {
    about: "Your company as cards, one box per team: who reports to whom.",
    help: lines(
      "Drag a card to move it; the place is saved for this company.",
      "Drop it into another box, or onto a card, to change who it reports to (Studio asks first).",
      "Drag a box by its label strip to move the whole team.",
      "Click selects, double-click opens the Inspector; A lays out, F fits, + and - zoom.",
    ),
  },
  "org-work": {
    about: "The company's issues, goals and projects, live from Paperclip.",
    help: lines(
      "One tab each; the lists refresh every 3 seconds while Org shows.",
      "Click a row to see it in the Inspector.",
      "With an agent selected, 'only <agent>' narrows the issues to its own.",
      "New issue assigns it on the spot: Paperclip wakes that agent.",
    ),
  },
  "org-inspector": {
    about: "The agent, issue, goal or project you clicked, and what you can do with it.",
    help: lines(
      "An agent: title, role, manager and budget; Save sends them to Paperclip.",
      "Wake, Pause or Resume and Terminate act at once (Terminate asks first); a toast says how it went.",
      "An issue: change its status or its assignee in place.",
      "Every item links to its own page in Paperclip.",
    ),
  },
};

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
