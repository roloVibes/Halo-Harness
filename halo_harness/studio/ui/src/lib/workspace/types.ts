// The workspace's types. A section declares its panels as PanelSpec[]; the
// user's arrangement is a Layout (one PanelLayout per panel id), kept per
// section in localStorage under `halo.studio.layout.<section>`.
import type { ComponentType } from "react";
import type { MotionState } from "../motion";

export const COLS = 24; // grid columns
export const ROW = 8; // px per grid row
export const STRIP_ROWS = 5; // a collapsed panel's height in rows (its title bar)
export const MIN_W = 4;
export const MIN_H = 8;
export const MOVE_ROWS = 4; // Alt+Up/Down moves (and Alt+Shift resizes) by this many rows

export type Face = "glance" | "detail";

export type PanelSpec = {
  id: string;
  title: string;
  /** Grid cells: x 0..23, w columns; y and h in 8 px rows. h <= 0 fills the visible height (h < 0 leaves -h rows below it). */
  x: number;
  y: number;
  w: number;
  h: number;
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
  /** Opens as a one-line strip in the full arrangement (`?open=all`; 3.3.2.0 R3: the section's default is quiet.ts's). */
  collapsed?: boolean;
  /** 3.3.2.0 R3: the section's one thing: it fills the stage by default, the other panels start as strips at the foot. */
  primary?: boolean;
  /** Not in the default arrangement: the palette or the header's "+" menu adds it (showPanel). */
  optional?: boolean;
  /** One line: what this panel is (3.3.2.0 R3: the first line of its ? help, the Inspector and the section help; not in the title bar). */
  about?: string;
  /** Three to five short lines, one per line: how to use it (the ? popover, the Inspector). */
  help?: string;
  /** Keep the body mounted while collapsed (an iframe keeps its state). */
  keepAlive?: boolean;
  testid?: string;
};

export type Rect = { x: number; y: number; w: number; h: number };

export type PanelLayout = Rect & {
  collapsed: boolean;
  floating: boolean;
  /** Floating position and size in px, relative to the workspace. */
  fx: number;
  fy: number;
  fw: number;
  fh: number;
  face: Face;
  z: number;
};

export type Layout = Record<string, PanelLayout>;

export type Gesture = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
