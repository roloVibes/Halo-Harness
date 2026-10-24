// The Pack Manager's shapes (3.2.0.0 R6): `GET pack/manager`, built by the
// server from the packs here and the places a bare id is looked for
// (halo_harness/packs/manager.py, packs/sources.py). Every line is in the
// words `halo pack` prints.

export type Permission = { name: string; needed_by: string[]; granted: boolean };
export type Requirement = { pack: string; version: string; met: boolean; have: string; running: boolean };
export type HealthRow = { pack: string; severity: "blocks" | "warns"; check: string; text: string; fix: string; path: string };
export type WorkflowInput = { name: string; type: string; required: boolean; default: unknown; description: string };
export type PackWorkflow = { ref: string; name: string; description: string; stages: string[]; inputs: WorkflowInput[] };
export type PackBio = { name: string; file: string; model: string; line: string; kind: string; needs: { need: string; granted: boolean }[] };
export type PackLineup = { name: string; file: string; members: { agent: string; role: string }[]; tiers: number; workflows: string[] };

export type PackRow = {
  id: string;
  name: string;
  version: string;
  /** enabled | enabled, not running | disabled | not installed (found in place) | a source folder */
  state: string;
  enabled: boolean;
  running: boolean;
  installed: boolean;
  scope: string;
  root: string;
  source: string;
  description: string;
  author: unknown;
  license: string | null;
  halo_api: string;
  halo: string;
  this_api: string;
  this_halo: string;
  capabilities: string[];
  requires: Requirement[];
  permissions: Permission[];
  granted: string[];
  requested: string[];
  health: HealthRow[];
  /** What keeps it from running here, in the doctor's words. */
  compat: string[];
  problems: string[];
  contributes_lines: string[];
  workflows: PackWorkflow[];
  bios: PackBio[];
  lineups: PackLineup[];
  sections: { id: string; title: string }[];
  settings: Record<string, unknown>;
  has_settings: boolean;
  /** 3.2.0.0 R7: the version `halo pack rollback` goes back to (kept as <id>.previous), or "". */
  previous: string;
};

export type SourcePack = { id: string; name: string; version: string; description: string; path: string; installed: boolean; problems: string[]; details?: PackRow };
export type Source = { source: string; kind: "folder" | "url" | "shipped"; configured: boolean; exists: boolean; problem: string; packs: SourcePack[] };

export type Manager = { version: number; halo: string; halo_api: string; packs: PackRow[]; sources: Source[]; problems: HealthRow[] };

/** What an action answered: the CLI's own lines. */
export type Done = { ok: boolean; lines: string[]; what: string };

/** 3.2.0.0 R7: what `halo pack update <id> --dry-run` said, shown before the Update runs. */
export type UpdatePreview = { id: string; ok: boolean; lines: string[] };
