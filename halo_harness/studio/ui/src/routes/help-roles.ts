// What each Roles panel is (`about`) and how to use it (`help`), 3.0.7.0 R2:
// the React section that replaces the framed classic page. Spread into HELP
// (help.ts); the section help lists the `about` lines.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const ROLES_HELP: Record<string, Help> = {
  "roles-lineups": {
    about: "Your lineups and the shipped ones; the active one is marked.",
    help: lines(
      "Click a lineup to open it on the canvas.",
      "New and Duplicate make your own copy; Delete asks first (shipped ones stay).",
      "Apply makes the open lineup the one new sessions use (it asks first).",
      "user / project: where New, Save and Delete write.",
    ),
  },
  "roles-graph": {
    about: "The open lineup as cards, one box per tier: who plays each part, on which model.",
    help: lines(
      "Drag a card into another tier box to move it there (the lineup saves); main stays in tier 0.",
      "Drag a bio from Bios onto the canvas to add it.",
      "A tier's label strip collapses or expands it. While a session runs, the cards whose agents work glow.",
      "Click the canvas, then A lays out, F fits, + / - zoom, the arrows nudge the selected card, Delete removes it.",
      "Ctrl+Z undoes an edit, Ctrl+Shift+Z redoes it, Mod+S saves.",
    ),
  },
  "roles-inspector": {
    about: "The selected card's slot, every section of the lineup, and what runs on the card now.",
    help: lines(
      "Assignment: the bio, role, alias, instances, routing words and a model override.",
      "Lineup: delegation, routing, budget, escalation, context, permissions, pipeline, acceptance, tiers.",
      "Each section is a small form; YAML edits the raw section instead.",
      "Live: the streams of the agents on the card, Steer, Pause, Stop, Pin; or its last runs, with replay.",
    ),
  },
  "roles-problems": {
    about: "What is wrong with the lineup as you edit it, each with its fix.",
    help: lines(
      "Blocks: Save answers 422 for these, or a run start stops on them (a dead model id, a bio with no tool).",
      "Warns: worth a look (an alias in no tier, a fallback on the same gateway).",
      "It re-reads after every edit, saved or not.",
      "Click a row to select its card.",
    ),
  },
  "roles-bios": {
    about: "The agent bios: who each card is, on which model, with which tools.",
    help: lines(
      "Click a bio to edit it below; drag one onto the canvas to add it to the lineup.",
      "The model table sorts by name, price or context and searches everything, best-for included.",
      "Test this model sends one short request and shows ok and the time, or the error.",
      "Save writes your copy (a shipped bio stays as it is); New, Duplicate, Delete.",
    ),
  },
  "roles-models": {
    about: "The model catalog the pickers read: per provider, and why it is empty when it is.",
    help: lines(
      "Refresh pulls every enabled provider's list again.",
      "A provider with a key but not enabled says so: halo providers enable <name>.",
      "Test a model by its ref, catalog or not.",
    ),
  },
};
