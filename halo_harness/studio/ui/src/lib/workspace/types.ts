// The workspace's types (3.6.0.0 R0a "room for everything in Studio": the grid of tiles became a stage). A section
// declares its panels as PanelSpec[]: one is the view's main thing (`role: "main"`, most of the room), the others
// open as a drawer beside it (`"drawer"`, full height, pushing the main thing, as wide as its content says:
// `contentW`) or as a tab of the main thing (`"tab"`). What is open is a Layout (one PanelLayout per panel id in the
// view), kept per section in localStorage under `halo.studio.layout.<section>` (persist.ts, v3).
import type { ComponentType } from "react";
import type { MotionState } from "../motion";

/** A drawer's width: its content's, between these (R2). */
export const DRAWER_MIN = 360;
export const DRAWER_MAX = 560;
export const DRAWER_STEP = 40; // Alt+Left/Right widen / narrow the focused drawer by this
/** The drawers together leave the main thing at least this share of the stage's width (R1). */
export const MAIN_SHARE = 0.6;
/** Breakpoints (R9): under WIDE one drawer at a time; under MID drawers float over the main thing; under PHONE the
 *  rail is a menu. */
export const BP_WIDE = 1440;
export const BP_MID = 1100;
export const BP_PHONE = 760;
/** A grid column of a pack's old cell declaration, in px: `w` columns -> contentW (the mapping rule). */
export const CELL_PX = 60;

export type Face = "glance" | "detail";
export type Role = "main" | "drawer" | "tab" | "dock";
export type Side = "left" | "right";

export type PanelSpec = {
  id: string;
  title: string;
  /** 3.6.0.0 R0a: the main thing, a drawer (the default), a tab of the main thing, or a bar docked at the main thing's
   *  foot (`dock`: always shown, as tall as its content; a prompt box). `primary` (3.3.2.0) = "main". */
  role?: Role;
  /** A drawer the view opens on its first load (its own default, e.g. a builder's list on the left); a person's
   *  choice, once kept, wins. */
  startOpen?: boolean;
  /** Its share of a stacked drawer's height in the full arrangement (`?open=all`, the drivers' door; default 1). */
  fullGrow?: number;
  /** A drawer's side (default right). */
  side?: Side;
  /** A drawer's width from its content, px (clamped to 360-560). */
  contentW?: number;
  /** A short live word for the view bar's button ("$0.42", "1"): a hook, called while the bar draws. */
  useCount?: () => string;
  /** Grid cells of a pack that declares its panels the old way (packs API 1.x): mapped by stage.ts (cells -> a
   *  drawer, `w` -> contentW = w x 60 px). Core specs do not set them. */
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  minW?: number;
  minH?: number;
  /** The face it opens on (default "detail", the full face; "glance" is the compact one). */
  face?: Face;
  /** Compact face (glance): what it is, one live indicator, one or two numbers. */
  glance: ComponentType;
  /** Full face (detail): the panel itself. Without it the panel only has the compact face. */
  detail?: ComponentType;
  /** Shown in the Inspector (the title bar's ... menu, Settings). */
  settings?: ComponentType;
  /** A hook returning the panel's state motion (called inside the panel). */
  useMotion?: () => MotionState;
  /** Closed even in the full arrangement (`?open=all`); every drawer starts closed on a normal load anyway. */
  collapsed?: boolean;
  /** 3.3.2.0 R3: the section's one thing; the same as `role: "main"`. */
  primary?: boolean;
  /** Not in the view until a door, the view bar's "more" or the palette adds it (showPanel). */
  optional?: boolean;
  /** One line: what this panel is (the first line of its ? help, the Inspector and the section help). */
  about?: string;
  /** Three to five short lines, one per line: how to use it (the ? popover, the Inspector). */
  help?: string;
  /** Keep the body mounted while closed (an iframe keeps its state). */
  keepAlive?: boolean;
  testid?: string;
};

/** One panel in the view: `collapsed` = a closed drawer, or a tab (or the main thing) not shown now. */
export type PanelLayout = {
  collapsed: boolean;
  face: Face;
  /** A drawer's width set by hand (px); absent: its contentW. */
  width?: number;
  /** When it was opened last (the oldest open drawer closes first when the room runs out). */
  z: number;
};

export type Layout = Record<string, PanelLayout>;
