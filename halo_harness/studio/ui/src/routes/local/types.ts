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
  managed?: Managed; // 3.3.5.0 R5: a server Halo started (source "managed server")
};
export type Managed = {
  id: string; pid: number | null; port: number; model: string; model_path: string; flags: ServeFlags; sources: Record<string, string>;
  ready: boolean; alive: boolean; keep: boolean; log: string; stop_cli: string; log_cli: string;
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
// 3.3.5.0 R2: the Library's rows (studio/models_library_api.py; models_library/rows.py's LibraryRow).
export type LibFit = Fit & { numbers?: { weights: number; kv: number; projector: number; total: number; budget: number; others: number; others_from: string; window: number; kv_cache: string } | null; estimate?: boolean; shape_source?: string };
export type LibRow = {
  source: "ollama" | "hf"; id: string; tag_or_file: string; name: string; model: string; family: string; params: number | null;
  quant: string; size_bytes: number | null; weights_bytes: number | null; projector_bytes: number; capabilities: string[];
  context: number | null; downloads: number | null; updated: string; license: string; gated: boolean | string; description: string;
  pull_line: string; alt_line?: string; kind: string; key: string; sources: Record<string, string>; estimate?: boolean;
  card: CardView; fit: LibFit; intent: Record<string, number | null>;
  installed?: string[]; pull_target?: string; // 3.3.5.0 R3: the hosts that have it; what Pull asks for
  on_disk?: string[]; // 3.3.5.0 R5: the model folders a hub row (or its file) is downloaded into
};
export type LibHost = { name: string; max_ctx: number | null; url: string };
export type LibraryAnswer = {
  rows: LibRow[]; total: number; page: number; pages: number; per: number; cached_at: number | null;
  sources: { ollama?: string; hf?: string }; notes: { ollama?: string; hf?: string }; window: number;
  host: { name: string | null; max_ctx: number | null; card: boolean }; hosts: LibHost[]; intents: Intent[]; intent: string;
  snapshot: { taken: string };
};
export type LibDetail = { source: string; id: string; rows: LibRow[]; note: string; about: Record<string, unknown>; window: number; host: string | null };
// 3.3.5.0 R3: Ollama, controlled (studio/local_control_api.py, studio/local_pull_job.py, studio/local_uses.py).
export type PullJob = {
  job: string; host: string; name: string; status: string; digest: string | null; total: number | null; completed: number | null;
  percent: number | null; speed: number | null; eta: number | null; done: boolean; error: string | null; ok: boolean;
  cancelled: boolean; say: string; via: string; started: number; remote: boolean;
  kind?: "pull" | "download"; repo?: string; file?: string; dir?: string; path?: string | null; // 3.3.5.0 R5
};
export type Uses = {
  ref: string; model: string; host: string; lineups: { name: string; role: string }[]; roles: string[]; compaction: boolean;
  default_model: boolean; profiles: string[]; sessions: { id: string; title: string; live: boolean }[]; any: boolean; live: number; line: string;
};
export type ShowAnswer = {
  ok: boolean; say: string; cli: string;
  facts: { family: string | null; params: string | null; quant: string | null; format: string | null; parent: string | null; context: number | null } | null;
  show: { template?: string; parameters?: string; params?: Record<string, string>; license?: string; capabilities?: string[];
          details?: Record<string, unknown>; model_info?: Record<string, unknown>; modified_at?: string; system?: string } | null;
};
export type TwinPlan = { ok: boolean; dry?: boolean; twin: string; ref: string; window: number; layers: number; line: string; cost: string; cli: string; say?: string };
// 3.3.5.0 R5: Hugging Face local (studio/local_hf_api.py, local_server_api.py, local_hf_view.py).
export type ServeFlags = { window: number; ngl: number; parallel: number; kv_type: string | null; flash_attn: boolean; num_predict: number | null };
export type HfServed = { id: string; port: number; ready: boolean; alive: boolean; kind: string; url: string };
export type HfModel = {
  key: string; path: string; dir: string; repo: string; file: string; model: string; kind: string; size: number; parts: number;
  hub: boolean; quant: string; context: number | null; card: CardView; fit: LibFit; fits: Record<string, { level: string; why: string }>;
  served: HfServed[]; ref: string | null; sources: Record<string, string>; cli: { serve: string; rm: string };
};
export type HfDir = { path: string; exists: boolean; size: number; models: HfModel[]; partial: { repo: string; bytes: number; files: number }[] };
export type HfDirs = { dirs: HfDir[]; window: number; host: string | null; hosts: { name: string; card: boolean; here: boolean }[] };
export type ServePlan = {
  ok: boolean; dry?: boolean; runtime: string; model: string; flags: ServeFlags; sources: Record<string, string>; notes: string[];
  host: string | null; layers: number | null; trained: number | null; argv: string[]; ref: string; cli: string;
  id?: string; port?: number; url?: string; ready?: boolean; say?: string; log?: string;
};
export type Licence = { license: string; gated: boolean | string; line: string; prompt: string };
export type DlPlan = { repo: string; file: string; kind: string; quant: string; total: number; commit: string; files: { name: string; size: number | null }[] };
