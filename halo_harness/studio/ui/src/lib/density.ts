// The density setting (Halo 3.3.2.0 R3): comfortable (the default) or compact, the two token sets in
// styles/tokens.css (`data-density` on <html>: spacing and the type scale; the colours stay). The header's
// toggle and the palette's "Density: compact / comfortable" set it; remembered per browser as
// `halo.studio.density` (a private window simply starts comfortable).
import { createStore, useStore } from "./store";

export type Density = "comfortable" | "compact";

export const DENSITY_KEY = "halo.studio.density";

function saved(): Density {
  try {
    return localStorage.getItem(DENSITY_KEY) === "compact" ? "compact" : "comfortable";
  } catch {
    return "comfortable";
  }
}

function apply(d: Density): void {
  try {
    document.documentElement.dataset.density = d;
  } catch {
    /* no document (a test without a DOM) */
  }
}

export const density = createStore<{ density: Density }>({ density: saved() });
apply(density.get().density);

export function setDensity(d: Density): void {
  try {
    localStorage.setItem(DENSITY_KEY, d);
  } catch {
    /* private window: not remembered */
  }
  apply(d);
  density.update(() => ({ density: d }));
}

export function toggleDensity(): void {
  setDensity(density.get().density === "compact" ? "comfortable" : "compact");
}

export function useDensity(): Density {
  return useStore(density, (s) => s.density);
}
