// The shapes the Local section's routes answer (studio/local_api.py, 3.3.5.0 R1).
import type { Fit } from "../../lib/ui/FitMeter";
import type { CardView } from "../shared/ModelCard";

export type Holder = { name: string | null; bytes: number | null; kind: "model" | "process" };
export type Sample = {
  host: string; url: string | null; t: number; gpu: number | null; vram_used: number | null; vram_total: number | null;
  holder: string | null; holders: Holder[]; ram_used: number | null; ram_total: number | null; cpu: number | null;
  temp: number | null; others: number | null; unified?: boolean; from?: string | null; sources: Record<string, string>;
};
export type TRow = {
  id: string; type: "call" | "event"; t: number | null; at?: string; host: string; model: string | null; from?: string | null;
  kind: string; prompt_in?: number | null; estimate?: number | null; reply_out?: number | null; window?: number | null;
  window_source?: string | null; trimmed?: boolean; cut?: boolean; status?: number | string | null; ok?: boolean;
  tok_s?: number | null; fitted?: boolean; switched_from?: string | null; bytes_in?: number | null; bytes_out?: number | null;
  error?: string | null; say?: string; severity?: string; notify?: boolean;
};
export type Bucket = { t: number; calls: number; trims: number; cuts: number; errors: number; bytes_in: number; bytes_out: number };
export type Traffic = { rows: TRow[]; events: TRow[]; spark: Record<string, Bucket[]>; since_s: number; hosts: string[]; at: number };
export type Loaded = { model: string | null; size: number | null; size_vram: number | null; vram_pct: number | null; expires: string | null; context_length: number | null };
export type PlanChoice = { kind: string; says: string; lose: string; fits: boolean; changes: { key: string; field: string; to: unknown }[] };
export type Controls = { ok: boolean; via: string; why: string; member?: string; member_host?: string };
export type HostCard = {
  name: string; url: string; kind: string; source: string; version: string | null; served_here: boolean; served_by: string;
  loaded: Loaded[]; card_lines: string[]; profiles: Record<string, { num_ctx?: number; num_predict?: number; keep_alive?: string | number; by?: string }>;
  users: { from: string | null; calls: number }[]; finding: string | null; findings: number;
  plan: { says: string; fits_now: boolean | null; chosen: PlanChoice | null } | null; models: string[]; controls: Controls;
};
export type ModelEntry = {
  model: string; ref: string; card: CardView; fit: Fit; size: number | null;
  profile: { num_ctx?: number; num_predict?: number; keep_alive?: string | number; by?: string; note?: string } | null;
  loaded: { size_vram: number | null; size: number | null; expires: string | null; context_length: number | null } | null;
  intent: Record<string, number | null>;
};
export type Intent = { id: string; title: string; why: string };
export type ModelsAnswer = { hosts: { name: string; kind: string; url: string; models: ModelEntry[] }[]; intents: Intent[]; at: number };
export type Said = { ok: boolean; text: string; undo?: number };
