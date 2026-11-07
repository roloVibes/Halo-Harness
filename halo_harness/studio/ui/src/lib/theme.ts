// One theme for the terminal and Studio (3.3.12.0 R1). `theme` in
// ~/.halo/config.json names a palette of the registry (halo_harness/themes):
// the server paints the first frame in it (`data-theme` on <html>,
// studio/theme_boot.py), `GET settings/themes` gives the ten with their
// tokens, and a choice here (the header's menu, the palette, Settings ->
// Themes) writes the key through the settings route, so `/theme`, `halo
// config set theme`, Settings and the header all move one value. Unset is
// "follow the system" (`auto`: holo on a dark system, paper on a light one).
// A change made elsewhere (`files_changed` for config.json) is read again.
// The per-browser choice of before (halo.studio.theme) is read once: written
// to the key when the key is unset, then dropped.
import { api, ApiError } from "./api";
import { onFilesChanged } from "./filesLive";
import { createStore, studio, toast, useStore } from "./store";

export type Tokens = Record<string, string>;
export type Palette = { id: string; label: string; posture: "dark" | "light"; tokens: Tokens; daltonized: Tokens };
export type ThemesInfo = {
  palettes: Palette[];
  modifiers: string[];
  follow: { dark: string; light: string };
  theme: string | null;
  posture: string;
  saved: string | null;
};

/** "Follow the system": the key unset, `data-theme="auto"`. */
export const FOLLOW = "auto";
export const MODIFIERS = ["daltonized", "ansi"] as const;
/** The swatch row's tokens, in the order a swatch draws them. */
export const SWATCH = ["surface", "text", "accent", "accent2", "ok", "warn", "bad"] as const;

type ThemesState = { info: ThemesInfo | null; error: string; preview: string };
export const themes = createStore<ThemesState>({ info: null, error: "", preview: "" });

export function useThemes<S>(select: (s: ThemesState) => S): S {
  return useStore(themes, select);
}

/** (palette id, modifier) of a theme name; ("", "") for "follow the system". */
export function splitTheme(name: string): [string, string] {
  if (!name || name === FOLLOW) return ["", ""];
  for (const mod of MODIFIERS) if (name.endsWith(`-${mod}`)) return [name.slice(0, -mod.length - 1), mod];
  return [name, ""];
}

/** The theme name of a palette with a modifier ("" = none). */
export function joinTheme(id: string, mod: string): string {
  return mod ? `${id}-${mod}` : id;
}

export function systemPosture(): "dark" | "light" {
  try {
    return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** The palette a theme name draws (follow: the system's pick); undefined before the registry is read. */
export function paletteOf(name: string): Palette | undefined {
  const info = themes.get().info;
  if (!info) return undefined;
  const id = name === FOLLOW || !name ? info.follow[systemPosture()] : splitTheme(name)[0];
  return info.palettes.find((p) => p.id === id);
}

/** Draw the page in `name` (a theme name or FOLLOW) without saving anything. */
export function paint(name: string): void {
  document.documentElement.dataset.theme = name || FOLLOW;
}

/** Preview `name` on the page (hover); null puts the saved one back (leave, Esc). */
export function previewTheme(name: string | null): void {
  themes.update(() => ({ preview: name || "" }));
  paint(name || studio.get().theme);
}

let reading: Promise<void> | null = null;

/** Read the registry and the saved key; the page follows the key. */
export function loadThemes(): Promise<void> {
  if (!reading)
    reading = (async () => {
      try {
        const info = await api.get<ThemesInfo>("settings/themes");
        themes.update(() => ({ info, error: "" }));
        const want = info.theme || FOLLOW;
        if (studio.get().theme !== want) studio.update(() => ({ theme: want }));
      } catch (e) {
        themes.update(() => ({ error: e instanceof Error ? e.message : String(e) }));
      } finally {
        reading = null;
      }
    })();
  return reading;
}

/** Save `name` to `theme` (FOLLOW: the key removed) and draw it; false (and a toast) when the server said no. */
export async function chooseTheme(name: string): Promise<boolean> {
  try {
    if (name === FOLLOW) await api.post("settings/unset", { key: "theme" });
    else await api.post("settings/set", { key: "theme", value: name });
  } catch (e) {
    const why = e instanceof ApiError && e.problems.length ? e.problems[0] : e instanceof Error ? e.message : String(e);
    toast(`Theme not saved: ${why}`, "error", 6000);
    return false;
  }
  themes.update(() => ({ preview: "" }));
  studio.update(() => ({ theme: name }));
  paint(name);
  void loadThemes();
  return true;
}

const LEGACY_KEY = "halo.studio.theme";

/** The per-browser choice of before 3.3.12.0: dark was holo, light the Latte palette (claude-light). */
function adoptLegacy(info: ThemesInfo): void {
  let old = "";
  try {
    old = localStorage.getItem(LEGACY_KEY) || "";
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    return;
  }
  const name = old === "dark" ? "holo" : old === "light" ? "claude-light" : "";
  if (name && !info.saved) void chooseTheme(name);
}

let started = false;

/** Once per page: the registry, the legacy choice, and a re-read whenever config.json moves. */
export function startThemes(): void {
  if (started) return;
  started = true;
  onFilesChanged(["config"], () => void loadThemes());
  void loadThemes().then(() => {
    const info = themes.get().info;
    if (info) adoptLegacy(info);
  });
}
