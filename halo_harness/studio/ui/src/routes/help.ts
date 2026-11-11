// What each panel is (`about`, one line) and how to use it (`help`, a few
// short lines), spread into the PanelSpecs: Media here, a goal run's plan review
// in help-orchestra.ts (3.4.0.0 D: the rest of Orchestra's went with Runs), Fleet in help-fleet.ts (Design's, 3.0.7.0 R3, are the design pack's since 3.3.13.0 R2),
// Roles in help-roles.ts (3.0.7.0 R2; Team's help-team.ts went with its board, 3.3.16.0 R1),
// Session in help-session.ts (3.1.4.0 R2), Packs in help-packs.ts (3.2.0.0 R6), Setup in help-setup.ts (3.3.0.0 R1), Settings in help-settings.ts (3.3.3.0 R2), Local in help-local.ts (3.3.5.0 R1). 3.3.2.0 R3: the title
// line shows no `about`; the ? popover (its first line), the Inspector and the section help show both.
import { FLEET_HELP } from "./help-fleet";
import { RUN_HELP, type Help } from "./help-orchestra";
import { ROLES_HELP } from "./help-roles";
import { SESSION_HELP } from "./help-session";
import { PACKS_HELP } from "./help-packs";
import { SETUP_HELP } from "./help-setup";
import { SETTINGS_HELP } from "./help-settings";
import { LOCAL_HELP } from "./help-local";

const lines = (...l: string[]) => l.join("\n");

export const HELP: Record<string, Help> = {
  ...RUN_HELP,
  ...ROLES_HELP,
  ...FLEET_HELP,
  ...SESSION_HELP,
  ...PACKS_HELP, // 3.2.0.0 R6: the Pack Manager
  ...SETUP_HELP, // 3.3.0.0 R1: the Setup section
  ...SETTINGS_HELP, // 3.3.3.0 R2: the Settings section, one entry per group page
  ...LOCAL_HELP, // 3.3.5.0 R1: the Local section, one entry per page
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
      "The design pack's Render panel runs one into a design project.",
    ),
  },
};
