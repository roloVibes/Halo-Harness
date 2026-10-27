// Settings (Alt+9, 3.3.3.0 R2): every key of ~/.halo/config.json, the ones
// `halo config set` and a dozen features write, from one catalog
// (halo_harness/settings_catalog.py): the group rail on the left
// (SettingsRail.tsx), one group's page on the right (SettingsPage.tsx) with
// the search box in its head, one row per key (Row.tsx). Paged like Setup: no
// panel workspace, nothing to move or Arrange, and nothing opens on its own;
// the page lands on General or the group last open (pages.ts), a door's
// `?group=` on that group (door.ts).
import { useEffect } from "react";
import { adoptRemembered } from "./pages";
import { SettingsPage } from "./SettingsPage";
import { SettingsRail } from "./SettingsRail";
import { startSettings, useSettings } from "./store";

/** The section's view: the rail beside the open page. */
export function SettingsView() {
  const groups = useSettings((s) => s.groups.length);
  useEffect(() => {
    startSettings();
  }, []);
  useEffect(() => {
    if (groups) adoptRemembered();
  }, [groups]);
  return (
    <div className="st-room" data-testid="settings-room">
      <SettingsRail />
      <div className="st-scroll">
        <SettingsPage />
      </div>
    </div>
  );
}

/** The section's entry (the palette or a door may open a page before the view draws). */
export function enterSettings(): void {
  startSettings();
}
