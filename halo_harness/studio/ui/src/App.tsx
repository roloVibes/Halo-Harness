// The Studio shell: header with the section tabs, the rail, the section's
// workspace (each visited section stays mounted, so a framed page keeps its
// state), the Inspector, the status bar, the palette, the toasts and the
// "How this works" overlay (also each section's first-visit welcome); from
// 3.0.5.0 the Fleet pieces that work in every section: the hop keys, Live
// Roles' bridge to the framed pages (and the canvas replay), the mini
// stream and the Fleet dialogs (R4: take over, hand to, message, kick, a recording).
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
import { startFeed } from "./shell/feed";
import { useGlobalKeys } from "./shell/keys";
import { useLegacyMessages } from "./shell/legacy";
import { FleetDialogs } from "./routes/fleet/Dialogs";
import { PanelDialogs } from "./routes/fleet/PanelDialogs";
import { useFleetFrames } from "./routes/fleet/frames";
import { useHopKeys } from "./routes/fleet/hop";
import { FleetPip } from "./routes/fleet/Pip";

export function App() {
  const section = useStore(studio, (s) => s.section);
  const visited = useStore(studio, (s) => s.visited);
  const theme = useStore(studio, (s) => s.theme);
  const railOpen = useStore(studio, (s) => s.railOpen);
  const inspecting = useStore(studio, (s) => s.inspector !== null);
  useGlobalKeys();
  useHopKeys();
  useLegacyMessages();
  useFleetFrames();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => startFeed(), []);
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
      <FleetDialogs />
      <PanelDialogs />
      <Toasts />
    </div>
  );
}
