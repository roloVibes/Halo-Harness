// Where a pack's link or palette action goes (3.2.0.0 R3): a route is a
// section (a core one or the pack's own) and maybe one of its panels, which
// opens and takes the focus once the section's workspace is up; a url opens
// in a new tab (an http(s) or mailto address only, as the manifest checks).
// Files of a pack are read with the token header (`pack/<id>/file/...`).
import { useEffect, useState } from "react";
import { token } from "../../lib/api";
import { goSection, toast, type SectionId } from "../../lib/store";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";
import { usePacks } from "./store";
import type { PaletteEntry, Route } from "./types";

const SAFE = /^(https?:|mailto:)/i;

export function openRoute(r: Route): void {
  goSection(r.section as SectionId);
  const panel = r.panel;
  if (!panel) return;
  const go = (tries: number) => {
    if (layoutStore(r.section).get().layout?.[panel]) {
      patchPanel(r.section, panel, { collapsed: false }, false);
      focusPanel(r.section, panel);
    } else if (tries > 0) window.setTimeout(() => go(tries - 1), 120);
  };
  go(20);
}

export function openUrl(url: string): void {
  if (SAFE.test(url)) window.open(url, "_blank", "noopener,noreferrer");
}

export function runAction(a: PaletteEntry["action"]): void {
  if (a.kind === "route" && a.section) openRoute({ section: a.section, panel: a.panel });
  else if (a.kind === "url" && a.url) openUrl(a.url);
  else toast("This action names nothing Studio can open", "info");
}

/** One file of a pack as text (the api path from the registry), with the token header. */
export async function fetchText(path: string): Promise<string> {
  const res = await fetch(new URL(path, location.origin + "/"), { headers: { Authorization: "Bearer " + token() } });
  const text = await res.text();
  if (!res.ok) {
    let why = text;
    try {
      why = String(JSON.parse(text).error || text);
    } catch {
      /* not JSON: the text itself */
    }
    throw new Error(why || `${res.status} ${res.statusText}`);
  }
  return text;
}

export type FileState = { text: string; error: string; loading: boolean };

/** A pack file's text, read again when the registry reloads (an update may have changed it). */
export function usePackFile(path: string | undefined): FileState {
  const reg = usePacks((s) => s.reg);
  const [st, setSt] = useState<FileState>({ text: "", error: "", loading: true });
  useEffect(() => {
    let live = true;
    if (!path) {
      setSt({ text: "", error: "this panel names no file", loading: false });
      return;
    }
    fetchText(path).then(
      (text) => live && setSt({ text, error: "", loading: false }),
      (e) => live && setSt({ text: "", error: e instanceof Error ? e.message : String(e), loading: false }),
    );
    return () => {
      live = false;
    };
  }, [path, reg]);
  return st;
}
