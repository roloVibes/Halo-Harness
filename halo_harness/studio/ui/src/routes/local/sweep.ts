// 3.6.0.25 T: the calls of "Find the best window" (studio/local_sweep_api.py; providers/local_sweep_run.py); the
// pure parts are sweepRows.ts. Every answer carries `cli`.
import { api, ApiError } from "../../lib/api";
import type { SweepAnswer } from "./sweepRows";

const enc = encodeURIComponent;
export const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export async function readSweep(host: string, model: string): Promise<SweepAnswer> {
  return api.get<SweepAnswer>(`local/host/${enc(host)}/sweep`, { model });
}

export async function startSweep(host: string, model: string): Promise<void> {
  await api.post(`local/host/${enc(host)}/sweep`, { model });
}

export async function stopSweep(host: string, model: string): Promise<string> {
  const r = await api.post<{ say?: string }>(`local/host/${enc(host)}/sweep/stop`, { model });
  return String(r.say || "");
}

export async function useInHalo(host: string, model: string): Promise<string> {
  const r = await api.post<{ say?: string }>(`local/host/${enc(host)}/sweep/use`, { model });
  return String(r.say || "done");
}
