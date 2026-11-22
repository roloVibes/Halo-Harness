// 3.6.0.12 SP: the one read of a map's body the truth block makes (TruthBlock.tsx useBody), built here so node can check
// it. The map the session runs on is read by its row's `map_scope` / `map_path` (as the drawing reads it, mapFiles.ts):
// the file of the SESSION's project, never Studio's folder's map of that name. A map that is not the session's own
// (the row names no file for it) is read by name, as before. `at` names the file read ("" by name), so a body held for
// one project's file is never shown for another's.
import { onMap } from "../crew/map/truthWords";

export type Where = { scope?: string | null; path?: string | null };

export function bodyAsk(name: string, a: string | null, where?: Where | null): { url: string; at: string } {
  const path = where?.path || "", scope = where?.scope || "";
  if (!path || !onMap(a, name)) return { url: `crew/map/${name}`, at: "" };
  const q = [scope ? `scope=${encodeURIComponent(scope)}` : "", `path=${encodeURIComponent(path)}`].filter(Boolean).join("&");
  return { url: `crew/map/${encodeURIComponent(name)}?${q}`, at: `${scope}|${path}` };
}
