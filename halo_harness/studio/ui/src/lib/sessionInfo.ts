// A live session as GET sessions and the feed name it (lib/store.ts re-exports it; 3.3.16.0 R1: moved out of
// lib/store.ts to keep it under the 250-line cap).
export type SessionInfo = {
  session_id: string;
  title?: string;
  mode?: string;
  kind?: string;
  cwd?: string;
  started?: number;
  pid?: number;
  /** From GET sessions (the control socket's status): waiting | busy | idle | unknown. */
  status?: string;
  busy?: boolean;
  pending?: Partial<Record<"permission" | "question" | "plan" | "approval", string[]>> | null;
  model?: string | null;
  /** 3.0.5.0 Fleet: sub-agents queued, running, waiting or paused right now. */
  agents?: number | null;
  harness?: { id?: string; name?: string; host?: string; user?: string; version?: string; os?: string } | null;
  project?: { root?: string; repo?: string | null; branch?: string | null; dirty?: boolean | null } | null;
  parent?: string | null;
};
