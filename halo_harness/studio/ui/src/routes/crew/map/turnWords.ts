// Main's lines on Auto (3.6.0.13 L3, R5, R8), letter for letter: TURN under main's NOW ("This turn: ..."), from main's row
// `turn` (3.6.0.10 M10: blank before the first turn, kept until his next message), and main's hover: "main · {model}",
// "This session: ..." (the row's `turn_total`), "Told it can start: {names}" (the status row's `kinds_told`, `kinds_more`);
// before the session's first request (nothing told yet) the hover is G5 (`g5Lines`) byte for byte. A part that is zero is
// left out; both zero: no line (nothing true to say). Pure: no React, no DOM (tests/test_map_groups.py runs it in node).
import { g5Lines, NAMES_SHOWN } from "./groupWords";
import { rowsOf } from "./nowRoom";

export type TurnCounts = { helpers?: number | null; tools?: number | null } | null | undefined;
/** What main was told it can start (the session row's `kinds_told` and `kinds_more`); null before the first request. */
export type Told = { names: string[]; more: number } | null | undefined;

const count = (k: number, one: string, many: string): string => `${k} ${k === 1 ? one : many}`;
function parts(c: TurnCounts): string {
  const h = Math.max(0, Math.floor(Number(c?.helpers) || 0)), t = Math.max(0, Math.floor(Number(c?.tools) || 0));
  return [h ? `started ${count(h, "helper", "helpers")}` : "", t ? `used ${count(t, "tool", "tools")} itself` : ""]
    .filter(Boolean).join(" · ");
}

/** TURN: "This turn: started {h} helpers · used {t} tools itself" ("" before the first turn or with both counts zero). */
export const turnLine = (turn: TurnCounts): string => { const p = parts(turn); return p ? `This turn: ${p}` : ""; };
/** Main's hover: "This session: started {H} helpers · used {T} tools itself" ("" with both counts zero). */
export const sessionLine = (total: TurnCounts): string => { const p = parts(total); return p ? `This session: ${p}` : ""; };

/** R5: TURN's longest usual words; its rows are held from the first draw (12/17 mono, L2b's 7.2 px a character). */
export const TURN_SAMPLE = turnLine({ helpers: 12, tools: 14 });
/** TURN's held rows in a text `width`: two at 224 px (Agents), three at 160 px (Session's 184 px box). */
export const turnRows = (width: number): number => rowsOf(TURN_SAMPLE, "", width);

/** Main hovered on Auto. `told` null (a session before its first request): G5, "Can hand work to: {names}". */
export function mainHover(model: string, names: string[], told: Told, total: TurnCounts): string[] {
  if (!told) return g5Lines(model, names);
  const head = model ? `main · ${model}` : "main";
  const more = Math.max(0, told.names.length - NAMES_SHOWN) + Math.max(0, Math.floor(Number(told.more) || 0));
  const said = told.names.length ? `Told it can start: ${told.names.slice(0, NAMES_SHOWN).join(", ")}${more > 0 ? ` and ${more} more` : ""}` : "";
  return [head, sessionLine(total), said].filter((x) => x !== "");
}
