// The picker's small state (3.4.1.3): the providers' status read once (the group heads' state lines and the empty
// line), and which provider groups are folded (kept per browser for a picker with a `foldKey`, Setup's page).
import { useEffect } from "react";
import { useModels } from "../../crew/models/store";
import { loadModelsStatus } from "../../crew/models/sync";
import type { ModelsStatus } from "../../crew/models/types";

let asked = false;

export function useStatusOnce(): ModelsStatus | null {
  const st = useModels((s) => s.modelsStatus);
  useEffect(() => {
    if (!st && !asked) {
      asked = true;
      void loadModelsStatus();
    }
  }, [st]);
  return st;
}

export function readFolds(key?: string): Record<string, boolean> {
  if (!key) return {};
  try {
    const v = JSON.parse(window.localStorage.getItem(key) || "{}");
    return v && typeof v === "object" ? (v as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

export function saveFolds(key: string | undefined, v: Record<string, boolean>): void {
  if (!key) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* a private window keeps it for this visit only */
  }
}
