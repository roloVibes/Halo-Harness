// The Map tab's shapes (3.6.0.0 R3): a map/1 file (halo_harness/crew/formats.py), a row of GET crew/maps and the answer
// of GET crew/map/<name> (studio/crew_map_api.py), with what each box holds.
import type { When } from "../types";

export type LineWhen = When | "main-decides";
export type MapBoxFile = { id: string; agent?: string | string[]; workflow?: string };
export type MapLine = { from: string; to: string; when?: LineWhen };
export type MapFile = { format?: string; name: string; boxes: MapBoxFile[]; lines: MapLine[]; main?: { agent: string }; caps?: { session_usd?: number } };

export type MapRow = { name: string; scope: "yours" | "project" | "starter"; in_use: boolean; problems: string[]; boxes: number; lines: number };

export type AgentFact = { name: string; model?: string; does?: string; careful?: string; uses?: string[]; missing?: boolean };
export type FlowFact = { name: string; for?: string; missing?: boolean; steps?: { name: string; agents: string[] }[] };
export type BoxFacts = { kind: "agent" | "workflow"; names: string[]; facts: (AgentFact & FlowFact)[] };

export type MapDetail = {
  map: MapFile;
  scope: MapRow["scope"];
  writable: boolean;
  in_use: boolean;
  problems: string[];
  boxes: Record<string, BoxFacts>;
  main: { agent: string; model?: string; does?: string };
};

/** A box as the page draws it: on the map or under "Not connected yet"; `ghost` = the builder's preview. */
export type DrawBox = { id: string; kind: "agent" | "workflow"; name: string; names: string[]; ghost?: boolean; isNew?: boolean; main?: boolean;
  /** 3.6.0.0 R4: a helper the running session made up (dashed, beside the box that started it), its agent id */
  helper?: string };
export type DrawLine = MapLine & { ghost?: boolean; helper?: boolean };

export const NEEDS: [string, string][] = [["pdf", "a PDF"], ["images", "an image"], ["audio", "audio"], ["video", "video"], ["code", "code"], ["review", "a review"]];

export function whenWords(w?: LineWhen): string {
  if (!w || w === "main-decides") return "main decides per task";
  if (w === "always") return "always";
  if (w === "ask") return "only when I ask";
  if ("needs" in w) return `needs ${w.needs.map((n) => (NEEDS.find(([k]) => k === n) || [n, n])[1]).join(", ")}`;
  return `says ${w.says.join(", ")}`;
}

export const boxName = (b: MapBoxFile): string => b.workflow || (Array.isArray(b.agent) ? b.agent.join(", ") : b.agent || b.id);
export const boxKind = (b: MapBoxFile): "agent" | "workflow" => (b.workflow ? "workflow" : "agent");
