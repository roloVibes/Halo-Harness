// The palette's theme commands (3.3.12.0 R1): "Theme: follow the system" and
// one "Theme: <id>" per palette of the registry (its label as the hint), each
// writing `theme` in ~/.halo/config.json like the header's menu; a modifier on
// now stays on. The registry is read the first time the palette asks.
import type { Command } from "./commands";
import { chooseTheme, FOLLOW, joinTheme, loadThemes, splitTheme, themes } from "../lib/theme";
import { studio } from "../lib/store";

export function themeCommands(): Command[] {
  const info = themes.get().info;
  if (!info) void loadThemes();
  const mod = splitTheme(studio.get().theme)[1];
  const out: Command[] = [
    { id: "theme-follow", group: "View", label: "Theme: follow the system", hint: "holo on a dark system, paper on a light one",
      run: () => void chooseTheme(FOLLOW) },
  ];
  for (const p of info?.palettes || [])
    out.push({ id: `theme-${p.id}`, group: "View", label: `Theme: ${p.id}`, hint: `${p.posture} · ${p.label}`,
               run: () => void chooseTheme(joinTheme(p.id, mod)) });
  return out;
}
