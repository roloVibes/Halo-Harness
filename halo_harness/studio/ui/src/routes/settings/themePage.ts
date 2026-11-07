// Settings -> Themes' behaviour (3.3.12.0 R1; the view is Themes.tsx, and this
// file is not themes.ts because a case-blind disk would read ./Themes as it): a
// palette under the pointer is previewed on the whole page (lib/theme.ts
// previewTheme, the key untouched); Esc, the pointer leaving the list, or
// leaving the page puts the saved theme back. A click saves (chooseTheme). The
// modifiers are two toggles: a name carries at most one, so turning one on
// turns the other off.
import { useEffect } from "react";
import { chooseTheme, FOLLOW, joinTheme, previewTheme, splitTheme, themes } from "../../lib/theme";
import { studio } from "../../lib/store";

/** While the page is open: Esc ends a preview; leaving the page ends one too. */
export function usePreviewRevert(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && themes.get().preview) {
        e.stopPropagation();
        previewTheme(null);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      if (themes.get().preview) previewTheme(null);
    };
  }, []);
}

/** The name a palette row previews and saves: the palette with the modifier on now. */
export function nameFor(id: string): string {
  const theme = studio.get().theme;
  return id === FOLLOW ? FOLLOW : joinTheme(id, theme === FOLLOW ? "" : splitTheme(theme)[1]);
}

export function preview(id: string): void {
  const name = nameFor(id);
  if (name !== studio.get().theme) previewTheme(name);
  else if (themes.get().preview) previewTheme(null);
}

export function endPreview(): void {
  if (themes.get().preview) previewTheme(null);
}

export function save(id: string): void {
  void chooseTheme(nameFor(id));
}

/** Turn modifier `mod` on or off for the palette saved now (nothing to modify while following the system). */
export function toggleModifier(mod: string, on: boolean): void {
  const theme = studio.get().theme;
  if (theme === FOLLOW) return;
  void chooseTheme(joinTheme(splitTheme(theme)[0], on ? mod : ""));
}
