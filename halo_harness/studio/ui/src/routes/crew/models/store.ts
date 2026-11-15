// The model catalog's store (3.6.0.0 R5: what the Roles store kept that the rest of Studio still reads -- the picker,
// Setup's default model, Settings' model fields, a goal run's plan review, Session's agent rows): the catalog rows (with
// best-for and the gym scores), the refs the picker offers beside them, the catalog's status, the last Analyze, the
// tool names, each "Test this model" result, and which action is busy. The lineups, bios, canvas and inspector state
// went with Cast (routes/roles/).
import { createStore, useStore } from "../../../lib/store";
import type { Analysis, GymScore, ModelRow, ModelsStatus, Probe } from "./types";

export type ModelsState = {
  models: ModelRow[];
  modelsLoaded: boolean;
  /** 3.1.4.0 R4: the refs GET models/fallback adds (in use, or the shipped list; not verified), and why GET models failed. */
  fallback: ModelRow[];
  modelsError: string;
  /** A Refresh ran on this page: the selects show what each provider said (until the page reloads). */
  justRefreshed: boolean;
  bestFor: Record<string, string[]>;
  gym: Record<string, GymScore>;
  /** 3.1.9.0 R1: the last Analyze on this page (POST models/analyze). */
  analysis: Analysis | null;
  modelsStatus: ModelsStatus | null;
  probe: Record<string, Probe | "running">;
  busy: string;
};

export const NONE: never[] = [];

export const models = createStore<ModelsState>({
  models: [], modelsLoaded: false, fallback: [], modelsError: "", justRefreshed: false, bestFor: {}, gym: {}, analysis: null,
  modelsStatus: null, probe: {}, busy: "",
});

export function useModels<S>(pick: (s: ModelsState) => S): S {
  return useStore(models, pick);
}

export function modelRow(s: ModelsState, ref: string): ModelRow | undefined {
  return ref ? s.models.find((m) => m.ref === ref) : undefined;
}

/** "$0.60 / $2.40" per 1M tokens, from the catalog row (the picker's price column). */
export function priceText(m: ModelRow | undefined): string {
  if (!m) return "price ?";
  const f = (v: number | null) => (typeof v === "number" ? "$" + (v < 1 ? v.toFixed(2) : v.toFixed(v < 10 ? 2 : 0)) : "?");
  return `${f(m.price_in)} / ${f(m.price_out)}`;
}
