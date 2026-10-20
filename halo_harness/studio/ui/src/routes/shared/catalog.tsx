// What every model control shares (3.1.4.0 R4): the short ref, a row's one
// price line, "refreshed <when>", loading the catalog once (and its status
// when it is empty), and CatalogLines -- the last Refresh's outcome per
// provider (ok and how many, or why not: no key, timed out, HTTP <status>,
// unreachable) and, while no live list exists, every provider status looked
// at and why it listed nothing. The Models panel and every ModelSelect show
// the same lines, so an empty dropdown always says why.
import { useEffect } from "react";
import { priceText, roles, useRoles } from "../roles/store";
import { loadModels, loadModelsStatus } from "../roles/sync";
import type { ModelRow } from "../roles/types";

/** The ref without its provider prefix (the provider is the option group). */
export const shortRef = (ref: string) => ref.replace(/^[a-z]{2,4}:/, "");

/** "or:vendor/model · $0.60 / $2.40 per 1M · ctx 200k" (an option's and the select's title). */
export function modelLine(m: ModelRow | undefined, ref = ""): string {
  if (!m) return ref ? `${ref} · not in the catalog` : "";
  return `${m.ref} · ${priceText(m)} per 1M · ctx ${m.context}${m.verified === false ? ` · ${m.detail}` : ""}`;
}

/** "just now", "4 min ago", "2 h ago", else the date. */
export function ago(ts: number | null | undefined): string {
  if (!ts) return "";
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleString();
}

let asked = false;

/** Read the catalog once (Roles' start reads it too); its status (the why lines) whenever nothing live is listed. */
export function useCatalog(): { models: ModelRow[]; fallback: ModelRow[]; loaded: boolean } {
  const models = useRoles((s) => s.models);
  const fallback = useRoles((s) => s.fallback);
  const loaded = useRoles((s) => s.modelsLoaded);
  const status = useRoles((s) => s.modelsStatus);
  useEffect(() => {
    if (!asked && !roles.get().modelsLoaded) {
      asked = true;
      void loadModels();
    }
  }, []);
  useEffect(() => {
    if (loaded && !models.length && !status) void loadModelsStatus();
  }, [loaded, models.length, status]);
  return { models, fallback, loaded };
}

/** The last Refresh, one line per provider; with no live list, what was looked at and why it listed nothing. */
export function CatalogLines({ empty }: { empty: boolean }) {
  const st = useRoles((s) => s.modelsStatus);
  const error = useRoles((s) => s.modelsError);
  const outcomes = st?.outcomes || [];
  const failing = empty ? (st?.looked_at || []).filter((l) => !l.ok) : [];
  const unset = failing.filter((l) => l.line.startsWith("not configured"));
  const looked = failing.filter((l) => !l.line.startsWith("not configured"));
  if (unset.length) looked.push({ name: "unset", label: "not configured", ok: false, line: `${unset.map((l) => l.label).join(", ")} (no key in the env file, the shell or settings.json)` });
  if (!error && !outcomes.length && !looked.length && !st?.refreshed_at) return null;
  return (
    <div className="msel-lines mono" data-testid="model-lines">
      {error && <div className="msel-line" data-ok="false" data-testid="model-error">{error}</div>}
      {st?.refreshed_at && <div className="msel-when muted" data-testid="model-refreshed">refreshed {ago(st.refreshed_at)}</div>}
      {outcomes.map((o) => (
        <div key={o.name} className="msel-line" data-ok={o.ok || undefined} data-testid="model-outcome" data-provider={o.provider}>
          {o.name}: {o.line}
        </div>
      ))}
      {looked.map((l) => (
        <div key={l.name + l.label} className="msel-line muted" data-testid="model-looked" data-provider={l.name}>
          {l.label}: {l.line}
        </div>
      ))}
    </div>
  );
}
