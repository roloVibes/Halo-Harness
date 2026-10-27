// The Studio shell: header, the rail (the sections as icons), the section's
// workspace (each visited section stays mounted, so it keeps its state), the
// Inspector, the status bar, the palette, the toasts and the
// "How this works" overlay; from
// 3.0.5.0 the Fleet pieces that work in every section: the hop keys, Live
// Roles (3.0.7.0 R2: the live agents into the Roles store for its React
// canvas), the mini stream and the Fleet dialogs (R4: take over, hand to,
// message, kick, a recording); 3.0.7.0 R3: the Design dialogs; R2:
// the Roles dialogs. 3.1.1.0 R1: the Glossary and "Start here" (a fresh home's offer of the guided first run).
// 3.1.1.0 R3: `?edit=` and the `focus` frame open a bio, a lineup or the Team (shell/edit.ts).
// 3.2.0.0 R3: the packs' sections and panels (routes/packs: the registry, reloaded on `pack_changed`).
// 3.3.2.0 R1 "Quiet Studio": nothing opens on its own when a section shows (the first-visit welcome is gone); the
// rail is icons (`data-rail="icons"`) or expanded (`"open"`), the inspector `data-inspector="closed"` until
// something opens it, and Focus (`data-focus="on"`: F, the header button, the palette) hides the rail, the
// inspector and the status bar.
import { useEffect } from "react";
import { studio, useStore } from "./lib/store";
import { Workspace } from "./lib/workspace/Workspace";
import { Toasts } from "./lib/ui";
import { sections, useSections } from "./routes";
import { startPacks } from "./routes/packs/store";
import { Header } from "./shell/Header";
import { Rail } from "./shell/Rail";
import { Inspector, useInspecting } from "./shell/Inspector";
import { StatusBar } from "./shell/StatusBar";
import { Palette } from "./shell/Palette";
import { SectionHelp } from "./shell/SectionHelp";
import { Glossary } from "./shell/Glossary";
import { StartHere } from "./shell/StartHere";
import { startFeed } from "./shell/feed";
import { installEdit } from "./shell/edit";
import { useFocusKey, useGlobalKeys } from "./shell/keys";
import { FleetDialogs } from "./routes/fleet/Dialogs";
import { PanelDialogs } from "./routes/fleet/PanelDialogs";
import { MissionDialogs } from "./routes/fleet/MissionDialogs";
import { useRolesLive } from "./routes/fleet/frames";
import { useHopKeys } from "./routes/fleet/hop";
import { FleetPip } from "./routes/fleet/Pip";
import { DesignDialogs } from "./routes/design/Dialogs";
import { RolesDialogs } from "./routes/roles/Dialogs";

export function App() {
  const section = useStore(studio, (s) => s.section);
  const visited = useStore(studio, (s) => s.visited);
  const theme = useStore(studio, (s) => s.theme);
  const rail = useStore(studio, (s) => s.rail);
  const focus = useStore(studio, (s) => s.focus);
  const inspecting = useInspecting();
  const all = useSections();
  useGlobalKeys();
  useHopKeys();
  useFocusKey(); // after the hop keys: an F a section already uses wins there
  useRolesLive();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => startFeed(), []);
  useEffect(() => installEdit(), []);
  useEffect(() => startPacks(), []);
  useEffect(() => {
    const def = sections().find((s) => s.id === section);
    document.title = def ? `${def.title} - Halo Studio` : "Halo Studio";
  }, [section]);

  return (
    <div className="app" data-rail={rail} data-inspector={inspecting ? "open" : "closed"} data-focus={focus ? "on" : "off"}>
      <Header />
      <Rail />
      <main className="stage" aria-label="Workspace">
        {all.filter((s) => visited.includes(s.id)).map((s) => (
          <div key={s.id} className="section-view" hidden={s.id !== section} data-section={s.id}>
            {s.view ? <s.view section={s.id} specs={s.panels} /> : <Workspace section={s.id} specs={s.panels} />}
          </div>
        ))}
      </main>
      <FleetPip />
      <Inspector />
      <StatusBar />
      <Palette />
      <SectionHelp />
      <Glossary />
      <StartHere />
      <FleetDialogs />
      <PanelDialogs />
      <MissionDialogs />
      <DesignDialogs />
      <RolesDialogs />
      <Toasts />
    </div>
  );
}
