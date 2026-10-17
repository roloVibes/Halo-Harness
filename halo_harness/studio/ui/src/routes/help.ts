// What each panel is (`about`, one line) and how to use it (`help`, a few
// short lines), spread into the PanelSpecs: Flow and Media here, Orchestra
// and the classic Roles canvas in help-orchestra.ts, Fleet in help-fleet.ts,
// Org and Design in help-org-design.ts (3.0.7.0 R3). The title bar shows
// `about`; the ? popover, the Inspector and the section help show both.
import { FLEET_HELP } from "./help-fleet";
import { CANVAS_HELP, ORCHESTRA_HELP, type Help } from "./help-orchestra";
import { DESIGN_HELP, ORG_HELP } from "./help-org-design";

const lines = (...l: string[]) => l.join("\n");

export const HELP: Record<string, Help> = {
  ...ORCHESTRA_HELP,
  ...CANVAS_HELP,
  ...FLEET_HELP,
  ...ORG_HELP,
  ...DESIGN_HELP,
  "flow-intake": {
    about: "Start a run: the brief, the platforms, the budget and the project.",
    help: lines(
      "Write what you want in BRIEF and pick the platforms to post on.",
      "Run waits for your OK on the render; Run with --yes accepts every gate.",
      "Dry run goes through every step but keeps the posts dry.",
      "Drop images or clips on ASSETS to give the roles material.",
    ),
  },
  "flow-graph": {
    about: "The run's steps in order; the diamond is the step that waits for you.",
    help: lines(
      "Faint = pending, a flowing edge = running, green = done, red = failed.",
      "An amber diamond means the run waits for your answer.",
      "Click a node to see that step in Step.",
      "The dashed arrow is redo: the render runs again with your instruction.",
    ),
  },
  "flow-renders": {
    about: "The pictures the render step made, and your OK on them.",
    help: lines(
      "Confirm keeps the render and moves on to posting.",
      "Type what to change and press Redo to render again.",
      "Stop ends the run here.",
      "The v1, v2 badges switch between the versions.",
    ),
  },
  "flow-step": {
    about: "One step in detail: cost, time, rounds and what it wrote.",
    help: lines(
      "It follows the step that needs you, else the running one.",
      "Click a node in Workflow to pick another step.",
      "The org step shows each position's text; the Art Director's prompt is marked.",
      "An org approval that waits for you is answered here.",
    ),
  },
  "flow-posts": {
    about: "One row per post the publish step made.",
    help: lines(
      "DRY RUN posts were written down, not sent.",
      "LIVE posts went out through Postiz and carry their post id.",
      "Set live: true on the flow's post step to post for real.",
    ),
  },
  "flow-metrics": {
    about: "Views, likes, comments and shares of each live post.",
    help: lines(
      "The measure step samples Postiz for the live posts.",
      "The small line is the trend over the samples.",
      "Dry-run posts have no numbers.",
    ),
  },
  "flow-log": {
    about: "Everything the run did, line by line, with the time it took.",
    help: lines(
      "Filter by step or by kind of line.",
      "Follow keeps the newest line in view.",
      "Click a step name to open that step in Step.",
      "Settings (the ... menu) switches between elapsed time and the clock.",
    ),
  },
  "flow-report": {
    about: "The run's summary: status, cost against the budget, steps, posts.",
    help: lines(
      "It fills in when the run ends; until then it shows the cost so far.",
      "Copy puts the text `halo flow report` prints on the clipboard.",
    ),
  },
  "media-status": {
    about: "Whether ComfyUI answers, its version and the GPU's free memory.",
    help: lines(
      "The dot ticks green on every check (every 15 s).",
      "Scan reads the server's models and saved workflows into Halo's cache.",
      "When it is red, the card says how to point Halo at your server.",
    ),
  },
  "media-models": {
    about: "The image, video, audio and upscale models on the ComfyUI server.",
    help: lines(
      "Pick a tab for the kind of output.",
      "Each row is a file with its family, precision and size.",
      "Encoders, LoRAs and VAEs sit under the supporting files.",
      "Press Scan in Media status after adding models.",
    ),
  },
  "media-workflows": {
    about: "The workflows a render can run: Halo's starters and your saved ones.",
    help: lines(
      "Click one to see the inputs a render can set (* marks a named input).",
      "Saved workflows come from ComfyUI's workflow browser.",
      "The Render panel uses the workflow you pick.",
    ),
  },
  "media-render": {
    about: "Run one ComfyUI workflow into a design project.",
    help: lines(
      "Pick the workflow, then change the named inputs (prompt, size, seed).",
      "Name the design project and the artboard to write into.",
      "Render queues it; the result shows here and in Design.",
    ),
  },
};
