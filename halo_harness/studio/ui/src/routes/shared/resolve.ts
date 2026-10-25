// What a role runs on (3.1.4.0 R4): `GET models/resolve?role=&lineup=`
// (studio/models_api.py) -- the model select's "the lineup's (<model>)" and
// "the default (<model>)", and the Team stage's "runs on". With a lineup: its
// card for the role and the model that card resolves to; with a role alone:
// the role table an Orchestra run uses (plus the active lineup's card for the
// role, for a link); with neither: the default model. One answer per
// (lineup, role) for the page's life; `forgetResolved()` drops them all
// (a lineup saved, a bio's model changed; 3.2.2.0 R6: and a lineup, bio or
// config.json moving on disk, the `files_changed` frames).
import { useEffect } from "react";
import { api } from "../../lib/api";
import { onFilesChanged } from "../../lib/filesLive";
import { createStore, useStore } from "../../lib/store";

export type Resolved = { ref: string; source: "lineup" | "roles" | "default" | "none"; role: string; lineup: string; card: string };

const cache = createStore<{ by: Record<string, Resolved | "loading"> }>({ by: {} });
const keyOf = (role: string, lineup: string) => `${lineup}|${role}`;

let watching = false;

async function load(role: string, lineup: string): Promise<void> {
  if (!watching) {
    watching = true;
    onFilesChanged(["lineups", "bios", "config"], () => forgetResolved());
  }
  const k = keyOf(role, lineup);
  if (cache.get().by[k]) return;
  cache.update((s) => ({ by: { ...s.by, [k]: "loading" } }));
  let got: Resolved;
  try {
    got = await api.get<Resolved>("models/resolve", { role, lineup });
  } catch {
    got = { ref: "", source: "none", role, lineup, card: "" };
  }
  cache.update((s) => ({ by: { ...s.by, [k]: got } }));
}

/** The model `role` runs on (in `lineup` when given); null until the answer arrives. */
export function useResolved(role: string, lineup = ""): Resolved | null {
  const k = keyOf(role.trim(), lineup.trim());
  const v = useStore(cache, (s) => s.by[k]);
  const missing = v === undefined; // forgotten (or never asked): ask again
  useEffect(() => {
    if (missing) void load(role.trim(), lineup.trim());
  }, [role, lineup, missing]);
  return v && v !== "loading" ? v : null;
}

/** Forget every answer: the next read asks again. */
export function forgetResolved(): void {
  cache.update(() => ({ by: {} }));
}
