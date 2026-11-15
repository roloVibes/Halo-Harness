// Reading the model catalog (3.6.0.0 R5, from the Roles store's sync): the catalog rows (3.1.4.0 R4: a failed read says
// why -- `modelsError` -- never a silent empty list), the refs the picker offers beside them (GET models/fallback),
// best-for and the gym scores (GET models/best-for, gym), and the catalog's status (GET models/status).
import { api, ApiError } from "../../../lib/api";
import { models } from "./store";
import type { GymScore, ModelRow, ModelsStatus } from "./types";

export const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));
const list = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

export async function loadModels(): Promise<void> {
  let error = "";
  const [rows, fallback, bestFor, gym] = await Promise.all([
    api.get<ModelRow[]>("models").catch((e) => ((error = `the catalog could not be read: ${msg(e)}`), [])),
    api.get<{ rows: ModelRow[] }>("models/fallback").catch(() => ({ rows: [] })),
    api.get<Record<string, string[]>>("models/best-for").catch(() => ({})),
    api.get<{ scores: Record<string, GymScore> }>("gym").catch(() => ({ scores: {} })),
  ]);
  if (!error && !Array.isArray(rows)) error = "the catalog came back in a shape Studio cannot read";
  models.update(() => ({ models: list(rows), fallback: list(fallback?.rows), modelsError: error, bestFor: bestFor || {}, gym: gym?.scores || {}, modelsLoaded: true }));
}

export async function loadModelsStatus(): Promise<void> {
  try {
    const st = await api.get<ModelsStatus>("models/status");
    models.update(() => ({ modelsStatus: st }));
  } catch {
    /* the picker says it could not ask */
  }
}
