// The Studio shell: header with the section tabs, the rail, the section's
// workspace (each visited section stays mounted, so it keeps its state), the
// Inspector, the status bar, the palette, the toasts and the
// "How this works" overlay (also each section's first-visit welcome); from
// 3.0.5.0 the Fleet pieces that work in every section: the hop keys, Live
// Roles (3.0.7.0 R2: the live agents into the Roles store for its React
// canvas), the mini stream and the Fleet dialogs (R4: take over, hand to,
// message, kick, a recording); 3.0.7.0 R3: the Design dialogs; R2:
// the Roles dialogs. 3.1.1.0 R1: the Glossary and "Start here" (a fresh home's offer of the ten-minute start).
// 3.1.1.0 R3: `?edit=` and the `focus` frame open a bio, a lineup or the Team (shell/edit.ts).
import { useEffect } from "react";
import { studio, useStore, welcomeIfNew } from "./lib/store";
import { Workspace } from "./lib/workspace/Workspace";
import { Toasts } from "./lib/ui";
import { SECTIONS } from "./routes";
import { Header } from "./shell/Header";
import { Rail } from "./shell/Rail";
import { Inspector } from "./shell/Inspector";
import { StatusBar } from "./shell/StatusBar";
import { Palette } from "./shell/Palette";
import { SectionHelp } from "./shell/SectionHelp";
import { Glossary } from "./shell/Glossary";
import { StartHere } from "./shell/StartHere";
import { startFeed } from "./shell/feed";
import { installEdit } from "./shell/edit";
import { useGlobalKeys } from "./shell/keys";
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
  const railOpen = useStore(studio, (s) => s.railOpen);
  const inspecting = useStore(studio, (s) => s.inspector !== null);
  useGlobalKeys();
  useHopKeys();
  useRolesLive();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => startFeed(), []);
  useEffect(() => installEdit(), []);
  useEffect(() => {
    const def = SECTIONS.find((s) => s.id === section);
    document.title = def ? `${def.title} - Halo Studio` : "Halo Studio";
    welcomeIfNew(section);
  }, [section]);

  return (
    <div className="app" data-rail={railOpen ? "open" : "closed"} data-inspector={inspecting ? "open" : "closed"}>
      <Header />
      <Rail />
      <main className="stage" aria-label="Workspace">
        {SECTIONS.filter((s) => visited.includes(s.id)).map((s) => (
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
