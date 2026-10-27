// The palette's Settings entries (3.3.3.0 R2): one "Settings: <title>" per
// catalog row, in the group named Settings (the section's own, after the other
// sections' groups). Running one opens Settings on the row's group, scrolls to
// the row and lights it for a moment (pages.ts openRow). The catalog is read
// the first time the palette asks (the entries are there from the next
// keystroke on); "Settings" itself is the Go to entry every section has.
import type { Command } from "../../shell/commands";
import { goSection } from "../../lib/store";
import { openRow } from "./pages";
import { loadCatalog, settings, startSettings } from "./store";

export function settingsCommands(): Command[] {
  const s = settings.get();
  if (!s.rows.length) {
    void loadCatalog();
    return [];
  }
  const title = Object.fromEntries(s.groups.map((g) => [g.id, g.title]));
  return s.rows.map((r) => ({
    id: "settings-" + r.key,
    group: "Settings",
    label: `Settings: ${r.title}`,
    hint: `${title[r.group] || r.group} · ${r.key}`,
    run: () => {
      startSettings();
      goSection("settings");
      openRow(r.key);
    },
  }));
}
