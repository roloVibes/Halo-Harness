// The palette's Media group: status, scan, models, workflows. The Media
// panels pop out over Local's page (3.3.13.0 R2: over the Design canvas before Design became a pack); from another
// section the palette goes to Local first. (A render into a design project is the design pack's Render panel.)
import { goSection, studio, toast } from "../../lib/store";
import { showPanel } from "../../lib/workspace/persist";
import { mediaPanels } from "./MediaPanels";
import { media, scan } from "./store";

export type MediaCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

/** Open a Media panel as a popped-out panel in Local; while ComfyUI does not answer, the status card
 *  (with the fix) opens instead. */
export function openMedia(want: string): void {
  const section = studio.get().section;
  const down = media.get().status?.reachable === false;
  const id = down ? "media-status" : want; // ComfyUI does not answer: the status card says how to fix it
  if (down && want !== id) toast("ComfyUI does not answer: Media status shows how to point Halo at it", "info", 4500);
  const spec = mediaPanels(0).find((p) => p.id === id);
  if (!spec) return;
  if (section === "local") {
    showPanel("local", spec, true);
    return;
  }
  goSection("local");
  window.setTimeout(() => showPanel("local", spec, true), 120);
}

export function mediaCommands(): MediaCommand[] {
  return [
    { id: "media-status", group: "Media", label: "Media: status", hint: "ComfyUI: reachable, version, VRAM, cache", run: () => openMedia("media-status") },
    { id: "media-scan", group: "Media", label: "Media: scan", hint: "read the server's models and saved workflows", run: () => void scan() },
    { id: "media-models", group: "Media", label: "Media: models", hint: "image, video, audio, upscale", run: () => openMedia("media-models") },
    { id: "media-workflows", group: "Media", label: "Media: workflows", hint: "the starters and the saved ones, each with its inputs", run: () => openMedia("media-workflows") },
  ];
}
