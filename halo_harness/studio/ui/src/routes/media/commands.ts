// The palette's Media group: status, scan, models, quick render. The Media
// panels pop out over the Design canvas; from another section the palette
// goes to Design first.
import { goSection, studio, toast } from "../../lib/store";
import { showPanel } from "../../lib/workspace/persist";
import { mediaPanels } from "./MediaPanels";
import { media, scan } from "./store";

export type MediaCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

/** Open a Media panel as a popped-out panel in Design; while ComfyUI does not answer, the status card
 *  (with the fix) opens instead. */
export function openMedia(want: string): void {
  const section = studio.get().section;
  const down = media.get().status?.reachable === false;
  const id = down ? "media-status" : want; // ComfyUI does not answer: the status card says how to fix it
  if (down && want !== id) toast("ComfyUI does not answer: Media status shows how to point Halo at it", "info", 4500);
  const spec = mediaPanels(0).find((p) => p.id === id);
  if (!spec) return;
  if (section === "design") {
    showPanel("design", spec, true);
    return;
  }
  goSection("design");
  window.setTimeout(() => showPanel("design", spec, true), 120);
}

export function mediaCommands(): MediaCommand[] {
  return [
    { id: "media-status", group: "Media", label: "Media: status", hint: "ComfyUI: reachable, version, VRAM, cache", run: () => openMedia("media-status") },
    { id: "media-scan", group: "Media", label: "Media: scan", hint: "read the server's models and saved workflows", run: () => void scan() },
    { id: "media-models", group: "Media", label: "Media: models", hint: "image, video, audio, upscale", run: () => openMedia("media-models") },
    { id: "media-render", group: "Media", label: "Media: quick render", hint: "a workflow into a design project", run: () => openMedia("media-render") },
  ];
}
