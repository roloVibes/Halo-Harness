// The shapes the Design section reads (3.0.7.0 R3): Studio's
// `/api/design/...` (studio/design_api.py, design_*_api.py) and the `design_turn` frames of
// the live feed (studio/design_turns.py). 3.0.7.0 R3b: knobs, the design
// system, a text picked in a prototype, the place of a new comment.

export type ProjectRow = { slug: string; name: string; created?: string; model?: string; artboards: number };

export type Artboard = {
  id: string;
  title?: string;
  kind: string;
  app?: string;
  created?: string;
  files: string[];
  /** Newest first. */
  versions: number[];
  latest: number;
  render: string;
  controls: Knob[];
};

/** One knob of an artboard's controls.json: a css: target applies at once, any other waits for the next turn. */
export type Knob = { name: string; kind?: string; target?: string; value?: unknown; min?: number; max?: number; step?: number; unit?: string; options?: unknown[] };

/** The design system (system.json): tokens by group, components, where it was synced from. */
export type SystemSheet = { name?: string; tokens?: Record<string, Record<string, string>>; components?: (string | { name?: string })[]; sources?: string[] };

/** A double-click on a text in a prototype (the frame's picker, studio/design_api_edit.py): where it sits and its box in the frame. */
export type TextPick = { aid: string; path: number[]; node: number; text: string; tag: string; x: number; y: number; w: number; h: number };

/** Where a new comment goes: percentages of the artboard's frame. */
export type PinAt = { aid: string; x: number; y: number };

export type Comment = { id: string; artboard: string; version: number; x: number; y: number; path?: string; text: string; resolved?: boolean; source?: string };

export type HistoryRow = {
  ts?: string;
  prompt?: string;
  model?: string;
  cost?: number | null;
  code?: number;
  versions?: [string, number][];
  elapsed?: number | null;
  tool_calls?: number | null;
  /** The model's reply (3.0.7.0 R3 logs it; older turns have none). */
  text?: string;
  cancelled?: boolean;
  /** A ComfyUI render from the Media panels. */
  app?: string;
  artboards?: string[];
};

export type Detail = {
  slug: string;
  meta: { name: string; model?: string; created?: string };
  artboards: Artboard[];
  comments: Comment[];
  system: SystemSheet;
  history: HistoryRow[];
  live_turn: string | null;
};

export type TurnEvent = {
  type?: string;
  message?: { content?: { type?: string; text?: string; name?: string; input?: unknown; input_line?: string }[] };
  result?: unknown;
  total_cost_usd?: number;
  cost_usd?: number;
  text?: string;
  code?: number;
  cost?: number | null;
  versions?: [string, number][];
};

export type TurnResult = { code: number; cost: number | null; text: string; versions: [string, number][]; error?: string; cancelled?: boolean; pins?: unknown[]; note?: string };

export type LiveTurn = { id: string; prompt: string; events: (TurnEvent | undefined)[]; done: boolean; result: TurnResult | null; label?: string };

export type Asset = { name: string; size: number; kind: string; path: string; thumb: string };

export type Pos = { x: number; y: number };

export type Contrast = { pairs: { fg: string; bg: string; fg_value: string; bg_value: string; ratio: number; aa: boolean; aaa: boolean; aa_large: boolean }[]; note: string };

export type DesignDialog =
  | { kind: "new" }
  | { kind: "rename"; aid: string }
  | { kind: "delete"; aid: string }
  | { kind: "export" }
  | { kind: "exported"; as: string; lines: string[] }
  | { kind: "handoff"; path: string }
  | { kind: "contrast"; aid: string; data: Contrast | null; error?: string }
  | { kind: "synced"; source: string; tokens: number; groups: [string, number][]; sources: string[] }
  | null;

export const EXPORTS: [string, string][] = [["folder", "Folder (a shareable site)"], ["html", "HTML"], ["png", "PNG"], ["svg", "SVG"], ["pdf", "PDF"]];
