// What each Packs panel is (`about`, one line) and how to use it (`help`, a
// few short lines), 3.2.0.0 R6 (the Pack Manager, docs/STUDIO-packs.md);
// routes/help.ts merges them into HELP and the section help lists the `about` lines.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const PACKS_HELP: Record<string, Help> = {
  "pm-installed": {
    about: "Every pack here: enabled or not, the grants given, its health; Enable, Disable, Update, Remove.",
    help: lines(
      "Each row is one pack: its id, name and version, its state, how many of the permissions it requests are granted, and the doctor's lines for it.",
      "Enable turns it on with the grants you picked in Details (halo pack enable <id> --grant ...); Disable turns it off and clears its grants.",
      "Update reads its source again: files you changed stay, the migration notes are listed. Remove asks first, then deletes only the pack's own files.",
      "Under the rows: the lines the last action printed, as halo pack prints them.",
    ),
  },
  "pm-sources": {
    about: "Where halo pack install <id> looks: packs.sources, then the packs Halo ships; Install from there.",
    help: lines(
      "Each box is one place, in the order a bare id is looked for: the folders and git urls of packs.sources, then the packs Halo ships.",
      "Install copies a pack in, disabled (into this repo's .halo/packs/ with \"into this repo\"); a git url is cloned only then.",
      "Add source puts a folder or a git url in packs.sources; Remove takes it out (installed packs stay).",
      "Click a pack's name to read it in Details before you install it.",
    ),
  },
  "pm-details": {
    about: "The selected pack: what it needs and requests, what keeps it from running, what it contributes.",
    help: lines(
      "The extension API and Halo ranges beside this Halo's, each pack it requires and whether that is met.",
      "What keeps it from running here is the doctor's words: an API range, a missing dependency, a fleet capability not available.",
      "Each permission it requests has a Grant toggle: on an enabled pack it grants (or takes back) at once; on a disabled one it is picked for Enable.",
      "What it contributes is the block halo pack inspect prints; the links open its section, its lineup in Roles and each workflow's Run.",
    ),
  },
  "pm-settings": {
    about: "The selected pack's settings: one field per key of its config.schema.",
    help: lines(
      "Save checks the values against the pack's schema, then writes packs.settings.<id> in ~/.halo/config.json.",
      "It works for a disabled pack too: set it up, then enable it.",
    ),
  },
  "pm-templates": {
    about: "The selected pack's lineups, bios and workflows, each with what you can do with it.",
    help: lines(
      "Preview opens a lineup or a bio in Roles, read-only; Clone copies it into your files; Customize clones it and opens your copy.",
      "Apply makes a lineup the one new sessions use (it asks first and names the pack).",
      "Run <workflow> opens Orchestra's new-run form with the workflow and its inputs filled in.",
      "A pack's templates are read in place while it runs, so enable it first.",
    ),
  },
};
