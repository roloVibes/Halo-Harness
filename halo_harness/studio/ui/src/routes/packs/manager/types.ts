// The Pack Manager's shapes (3.2.0.0 R6): `GET pack/manager`, built by the
// server from the packs here and the places a bare id is looked for
// (halo_harness/packs/manager.py, packs/sources.py). Every line is in the
// words `halo pack` prints.

/** 3.3.13.0 R2: `what` is the grant's one line (packs/grants.py WHAT: studio-routes "runs this pack's Python inside Studio's server"). */
export type Permission = { name: string; needed_by: string[]; granted: boolean; what?: string };
export type Requirement = { pack: string; version: string; met: boolean; have: string; running: boolean };
export type HealthRow = { pack: string; severity: "blocks" | "warns" | "info"; check: string; text: string; fix: string; path: string };
export type WorkflowInput = { name: string; type: string; required: boolean; default: unknown; description: string };
export type PackWorkflow = { ref: string; name: string; description: string; stages: string[]; inputs: WorkflowInput[] };
export type PackBio = { name: string; file: string; model: string; line: string; kind: string; needs: { need: string; granted: boolean }[] };
/** 3.3.10.0 R3: a lineup's workflow resolved: `<pack>/<name> -- <title>: <description>`, or "<name> (not found)". */
export type WorkflowLine = { ref: string; found: boolean; line: string };
export type PackLineup = { name: string; file: string; members: { agent: string; role: string }[]; tiers: number; workflows: string[];
  workflow_lines?: WorkflowLine[] };

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
  /** halo pack doctor's blocks and warns rows for it. */
  health: HealthRow[];
  /** 3.3.10.0 R3: its info rows (a note, never a problem: a fleet capability hidden on purpose). */
  notes: HealthRow[];
  /** 3.3.11.0 R3: how many of its Setup blocks are neither done nor skipped (0 while it is disabled). */
  setup_waiting?: number;
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
  /** 3.3.10.0 R2: a pack with policy hooks: the armed ones, its mode, the last verdict a session got and the counts. */
  policy?: PolicyBlock | null;
  /** 3.3.13.0 R3: its services as the supervisor runs them ("running since 09:12" / "stopped: <line>"). */
  services?: ServiceRow[];
};

export type ServiceRow = { name: string; key: string; state: string; line: string; description: string };

export type PolicyBlock = { armed: string[]; mode: string | null; last: string; last_ts: number | null; counts: Record<string, number> };

export type SourcePack = { id: string; name: string; version: string; description: string; path: string; installed: boolean; problems: string[]; details?: PackRow };
export type Source = { source: string; kind: "folder" | "url" | "shipped"; configured: boolean; exists: boolean; problem: string; packs: SourcePack[] };

export type Manager = { version: number; halo: string; halo_api: string; packs: PackRow[]; sources: Source[]; problems: HealthRow[] };

/** What an action answered: the CLI's own lines. */
export type Done = { ok: boolean; lines: string[]; what: string };

/** 3.2.0.0 R7: what `halo pack update <id> --dry-run` said, shown before the Update runs. */
export type UpdatePreview = { id: string; ok: boolean; lines: string[] };
