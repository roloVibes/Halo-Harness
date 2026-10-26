// What each panel is (`about`, one line) and how to use it (`help`, a few
// short lines), spread into the PanelSpecs: Media here, Orchestra
// in help-orchestra.ts, Fleet in help-fleet.ts, Design in
// help-design.ts (3.0.7.0 R3), Roles in help-roles.ts (3.0.7.0 R2), Team in help-team.ts (3.0.8.0 R2),
// Session in help-session.ts (3.1.4.0 R2), Packs in help-packs.ts (3.2.0.0 R6), Setup in help-setup.ts (3.3.0.0 R1). The title bar shows
// `about`; the ? popover, the Inspector and the section help show both.
import { FLEET_HELP } from "./help-fleet";
import { ORCHESTRA_HELP, type Help } from "./help-orchestra";
import { DESIGN_HELP } from "./help-design";
import { ROLES_HELP } from "./help-roles";
import { SESSION_HELP } from "./help-session";
import { TEAM_HELP } from "./help-team";
import { PACKS_HELP } from "./help-packs";
import { SETUP_HELP } from "./help-setup";

const lines = (...l: string[]) => l.join("\n");

export const HELP: Record<string, Help> = {
  ...ORCHESTRA_HELP,
  ...ROLES_HELP,
  ...FLEET_HELP,
  ...DESIGN_HELP,
  ...TEAM_HELP,
  ...SESSION_HELP,
  ...PACKS_HELP, // 3.2.0.0 R6: the Pack Manager
  ...SETUP_HELP, // 3.3.0.0 R1: the Setup section
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
