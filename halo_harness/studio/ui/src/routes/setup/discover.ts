// Find, Scan, Add and Measure in Setup's Ollama card (3.3.0.0 R5): the
// servers found here (`POST setup/ollama/find`, this machine's doors at once;
// `POST setup/ollama/scan`, the network sweep as a background job), the ticks,
// Add the ticked (`POST setup/ollama/add {urls}`: new `ollama.hosts` entries,
// never a host repointed, the first host stays the default; the answer is the
// fresh state, so the hosts table redraws, and the Models refresh runs so the
// new host's models list under `Ollama (<name>)`), then Measure the found
// models (`POST setup/ollama/measure {hosts, models}`: one calibration per
// model). Both jobs stream `setup` frames on the live feed
// (studio/setup_discover_jobs.py); while one runs the page also reads its
// latest frame every second, so a closed feed or a reload still catches up.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, toast, useStore } from "../../lib/store";
import { refreshModels } from "../roles/bioActions";
import { cards } from "./cards";
import { setup, showStatus, type SetupData } from "./store";

export type FoundRow = { url: string; name: string; version: string | null; models: string[]; configured: boolean; where: string };
export type JobState = "idle" | "running" | "done" | "stopped";
export type ScanFrame = { job: string | null; kind: "scan"; state: JobState; rows?: FoundRow[]; note?: string; notes?: string[]; elapsed?: number; running?: boolean };
export type MeasureFrame = {
  job: string | null;
  kind: "measure";
  state: JobState;
  host?: string;
  model?: string;
  index?: number;
  total?: number;
  line?: string;
  lines?: string[];
  summary?: string;
  elapsed?: number;
  running?: boolean;
};

type Discover = {
  rows: FoundRow[];
  notes: string[];
  ports: number[] | null;
  ticked: Record<string, boolean>; // by url
  busy: "" | "find" | "add" | "measure";
  scan: ScanFrame | null;
  measure: MeasureFrame | null;
  added: string[]; // the hosts Add wrote in this page, in order
  picks: Record<string, boolean>; // `<model>@<host>` -> ticked for Measure
};

export const discover = createStore<Discover>({ rows: [], notes: [], ports: null, ticked: {}, busy: "", scan: null, measure: null, added: [], picks: {} });

export function useDiscover<S>(select: (s: Discover) => S): S {
  return useStore(discover, select);
}

const msg = (e: unknown) => (e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)]);

/** Rows by url: a later answer replaces the row it names, the others stay. */
function merge(rows: FoundRow[]): void {
  discover.update((s) => {
    const by = new Map(s.rows.map((r) => [r.url, r]));
    rows.forEach((r) => by.set(r.url, r));
    return { rows: [...by.values()] };
  });
}

export const running = (f: { state: JobState; running?: boolean } | null) => !!f && (f.state === "running" || !!f.running);

function adoptScan(f: ScanFrame): void {
  discover.update(() => ({ scan: f }));
  if (f.state === "done" && f.rows) merge(f.rows);
}

function adoptMeasure(f: MeasureFrame): void {
  discover.update(() => ({ measure: f }));
}

let polling = 0;

/** While a job runs, read its latest frame every second (the feed may be closed; a reload lands mid-job). */
function poll(): void {
  if (polling) return;
  polling = window.setInterval(async () => {
    const s = discover.get();
    const kinds = [running(s.scan) && "scan", running(s.measure) && "measure"].filter(Boolean) as string[];
    if (!kinds.length) {
      window.clearInterval(polling);
      polling = 0;
      return;
    }
    for (const kind of kinds) {
      try {
        const f = await api.get<ScanFrame & MeasureFrame>(`setup/ollama/${kind}`);
        if (kind === "scan") adoptScan(f as ScanFrame);
        else adoptMeasure(f as MeasureFrame);
      } catch {
        /* the next tick asks again */
      }
    }
  }, 1000);
}

let started = false;

/** Once per page: the `setup` frames, and the latest jobs (a scan or a measure still running after a reload). */
export function startDiscover(): void {
  if (started) return;
  started = true;
  onEvent("setup", (frame) => {
    const d = frame.data as (ScanFrame | MeasureFrame) | null;
    if (!d || !d.kind) return;
    if (d.kind === "scan") adoptScan(d);
    else if (d.kind === "measure") adoptMeasure(d);
  });
  void (async () => {
    try {
      const [scan, measure] = await Promise.all([api.get<ScanFrame>("setup/ollama/scan"), api.get<MeasureFrame>("setup/ollama/measure")]);
      if (scan.job) adoptScan(scan);
      if (measure.job) adoptMeasure(measure);
      poll();
    } catch {
      /* the buttons still work */
    }
  })();
}

export async function findServers(): Promise<void> {
  discover.update(() => ({ busy: "find" }));
  try {
    const r = await api.post<{ rows: FoundRow[]; notes: string[]; ports: number[] }>("setup/ollama/find", {});
    merge(r.rows);
    discover.update(() => ({ notes: r.notes, ports: r.ports }));
    const fresh = r.rows.filter((x) => !x.configured).length;
    toast(r.rows.length ? `found ${r.rows.length} Ollama server${r.rows.length === 1 ? "" : "s"} on this machine, ${fresh} new` : "no Ollama server answered on this machine", "done", 4000);
  } catch (e) {
    toast(msg(e)[0], "error", 6000);
  } finally {
    discover.update(() => ({ busy: "" }));
  }
}

export async function scanNetwork(): Promise<void> {
  try {
    const r = await api.post<{ job: ScanFrame }>("setup/ollama/scan", {});
    adoptScan({ ...r.job, state: "running", running: true });
    poll();
  } catch (e) {
    toast(msg(e)[0], "error", 6000);
  }
}

export async function stopJob(kind: "scan" | "measure"): Promise<void> {
  try {
    await api.post(`setup/ollama/${kind}/stop`, {});
  } catch (e) {
    toast(msg(e)[0], "error", 6000);
  }
}

export function tick(url: string, on: boolean): void {
  discover.update((s) => ({ ticked: { ...s.ticked, [url]: on } }));
}

export function pickModel(ref: string, on: boolean): void {
  discover.update((s) => ({ picks: { ...s.picks, [ref]: on } }));
}

/** Add the ticked rows; the hosts table, the strip and the Models panel follow. */
export async function addTicked(): Promise<void> {
  const urls = discover.get().rows.filter((r) => !r.configured && discover.get().ticked[r.url]).map((r) => r.url);
  if (!urls.length) return;
  discover.update(() => ({ busy: "add" }));
  try {
    const r = await api.post<SetupData & { lines?: string[]; added: string[]; rows: FoundRow[] }>("setup/ollama/add", { urls });
    const { lines, added, rows, ...data } = r;
    setup.update(() => ({ data: data as SetupData }));
    showStatus(data as SetupData);
    merge(rows);
    const picks: Record<string, boolean> = {};
    rows.filter((x) => added.includes(x.name)).forEach((x) => x.models.forEach((m) => (picks[`${m}@${x.name}`] = true)));
    discover.update((s) => ({ ticked: {}, added: [...s.added, ...added.filter((n) => !s.added.includes(n))], picks: { ...s.picks, ...picks } }));
    cards.update((s) => ({ last: { ...s.last, "ollama-found": { ok: true, lines: lines || [] } } }));
    toast(lines?.[0] || "Added", "done", 4000);
    if (added.length) void refreshModels(); // the Models panel: each new host's models under Ollama (<name>)
  } catch (e) {
    cards.update((s) => ({ last: { ...s.last, "ollama-found": { ok: false, lines: msg(e) } } }));
    toast(msg(e)[0], "error", 6000);
  } finally {
    discover.update(() => ({ busy: "" }));
  }
}

/** Measure the ticked models (`<model>@<host>`), one calibration each. */
export async function measureTicked(): Promise<void> {
  const refs = Object.entries(discover.get().picks).filter(([, on]) => on).map(([ref]) => ref);
  const hosts = [...new Set(refs.map((r) => r.slice(r.lastIndexOf("@") + 1)))];
  if (!refs.length) return;
  discover.update(() => ({ busy: "measure" }));
  try {
    const r = await api.post<{ job: MeasureFrame }>("setup/ollama/measure", { hosts, models: refs });
    adoptMeasure({ ...r.job, state: "running", running: true });
    poll();
  } catch (e) {
    toast(msg(e)[0], "error", 6000);
  } finally {
    discover.update(() => ({ busy: "" }));
  }
}
