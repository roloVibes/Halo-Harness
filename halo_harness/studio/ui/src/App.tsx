// The Studio shell: header with the section tabs, the rail, the section's
// workspace (each visited section stays mounted, so a framed page keeps its
// state), the Inspector, the status bar, the palette and the toasts.
import { useEffect } from "react";
import { studio, useStore } from "./lib/store";
import { Workspace } from "./lib/workspace/Workspace";
import { Toasts } from "./lib/ui";
import { SECTIONS } from "./routes";
import { Header } from "./shell/Header";
import { Rail } from "./shell/Rail";
import { Inspector } from "./shell/Inspector";
import { StatusBar } from "./shell/StatusBar";
import { Palette } from "./shell/Palette";
import { startFeed } from "./shell/feed";
import { useGlobalKeys } from "./shell/keys";

export function App() {
  const section = useStore(studio, (s) => s.section);
  const visited = useStore(studio, (s) => s.visited);
  const theme = useStore(studio, (s) => s.theme);
  const railOpen = useStore(studio, (s) => s.railOpen);
  const inspecting = useStore(studio, (s) => s.inspector !== null);
  useGlobalKeys();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => startFeed(), []);
  useEffect(() => {
    const def = SECTIONS.find((s) => s.id === section);
    document.title = def ? `${def.title} - Halo Studio` : "Halo Studio";
  }, [section]);

  return (
    <div className="app" data-rail={railOpen ? "open" : "closed"} data-inspector={inspecting ? "open" : "closed"}>
      <Header />
      <Rail />
      <main className="stage" aria-label="Workspace">
        {SECTIONS.filter((s) => visited.includes(s.id)).map((s) => (
          <div key={s.id} className="section-view" hidden={s.id !== section} data-section={s.id}>
            <Workspace section={s.id} specs={s.panels} />
          </div>
        ))}
      </main>
      <Inspector />
      <StatusBar />
      <Palette />
      <Toasts />
    </div>
  );
}
