// The Design section's store (3.0.7.0 R3): the projects, the open one (its
// artboards, comments, history), the turn that runs now (its events from the
// live feed, or the poll when the feed is down), the message being written,
// the artboard card positions (the server's `layout/design:<slug>`), the
// version each card shows, the assets and the one open dialog. 3.0.7.0 R3b:
// the preview device (the Artboards panel's own setting, remembered under
// PANEL_KEY), the canvas tool (select, or comment: a click pins a comment),
// the comment being written and the pin opened, the text being edited, and
// the version chip a knob change made.
import { createStore, useStore, writeLocal } from "../../lib/store";
import { isDevice, type Device } from "./layout";
import type { Artboard, Asset, DesignDialog, Detail, HistoryRow, LiveTurn, PinAt, Pos, ProjectRow, TextPick } from "./types";

/** The Artboards panel's settings (its Inspector face): {device}. */
export const PANEL_KEY = "halo.studio.design.panel.design-artboards";

function savedDevice(): Device {
  try {
    const d = JSON.parse(localStorage.getItem(PANEL_KEY) || "{}").device;
    return isDevice(d) ? d : "desktop";
  } catch {
    return "desktop";
  }
}

export type DesignState = {
  started: boolean;
  projects: ProjectRow[] | null;
  slug: string;
  data: Detail | null;
  loading: boolean;
  error: string;
  turn: LiveTurn | null;
  draft: string;
  positions: Record<string, Pos>;
  posFor: string;
  /** The version a card shows (absent: the newest). */
  view: Record<string, number>;
  /** Bumped when an artboard changed, so its frame reloads. */
  bust: Record<string, number>;
  sel: string;
  assets: Asset[];
  dialog: DesignDialog;
  busy: string;
  /** Bumped to move the keyboard focus into the message box. */
  focusSend: number;
  device: Device;
  tool: "select" | "comment";
  pinAt: PinAt | null;
  /** The comment whose pin is open (its text and Resolve). */
  pinOpen: string;
  editing: TextPick | null;
  /** What the last knob change made, per artboard: "v3", or "next turn". */
  knobNote: Record<string, string>;
};

export const design = createStore<DesignState>({
  started: false,
  projects: null,
  slug: "",
  data: null,
  loading: false,
  error: "",
  turn: null,
  draft: "",
  positions: {},
  posFor: "",
  view: {},
  bust: {},
  sel: "",
  assets: [],
  dialog: null,
  busy: "",
  focusSend: 0,
  device: savedDevice(),
  tool: "select",
  pinAt: null,
  pinOpen: "",
  editing: null,
  knobNote: {},
});

export function setDevice(device: Device): void {
  design.update(() => ({ device }));
  writeLocal(PANEL_KEY, JSON.stringify({ device }));
}

export const setTool = (tool: DesignState["tool"]) => design.update(() => ({ tool, pinAt: null, pinOpen: "", editing: null }));

export function useDesign<S>(select: (s: DesignState) => S): S {
  return useStore(design, select);
}

export const NONE: never[] = [];
export const openDialog = (dialog: DesignDialog) => design.update(() => ({ dialog }));
export const closeDialog = () => design.update(() => ({ dialog: null }));
export const live = (s: DesignState) => !!s.turn && !s.turn.done;
export const showsStart = (s: DesignState) => s.projects !== null && s.projects.length === 0;

export function artboard(s: DesignState, aid: string): Artboard | undefined {
  return s.data?.artboards.find((a) => a.id === aid);
}

export const money = (n?: number | null) => (n == null ? "-" : "$" + Number(n).toFixed(n < 0.1 ? 4 : 2));
export const kb = (n: number) => (n < 1024 ? n + " B" : n < 1048576 ? Math.round(n / 1024) + " KB" : (n / 1048576).toFixed(1) + " MB");

/** What a turn changed, as "hero v2, logo v1". */
export const versionsLine = (vs?: [string, number][]) => (vs || []).map(([a, n]) => `${a} v${n}`).join(", ");

/** The raw file of an artboard (version `n`, 0 = the current files): the sandboxed /design-files/ route. */
export function fileUrl(slug: string, aid: string, file: string, n = 0, bust = 0): string {
  return `/design-files/${encodeURIComponent(slug)}/${encodeURIComponent(aid)}/${n ? "v" + n + "/" : ""}${encodeURIComponent(file)}${bust ? "?t=" + bust : ""}`;
}

export const assetUrl = (slug: string, name: string) => `/design-files/${encodeURIComponent(slug)}/_assets/${encodeURIComponent(name)}`;

/** The project's spend so far. */
export const spent = (h: HistoryRow[]) => h.reduce((n, x) => n + (Number(x.cost) || 0), 0);

/** One line for the status bar. */
export function statusLine(s: DesignState): string {
  const d = s.data;
  if (!d) return s.projects && !s.projects.length ? "no design project yet" : "";
  const open = d.comments.filter((c) => !c.resolved).length;
  return `project: ${d.meta.name} · ${d.artboards.length} artboard(s) · ${open} open comment(s) · ${money(spent(d.history))}${live(s) ? " · a turn runs" : ""}`;
}
