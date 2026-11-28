// 3.6.0.25 T: the pure parts of "Find the best window" (routes/local/SweepCard.tsx): the table's cells and the pick's
// mark, pinned by tests/test_local_bench_api.py in node (no import: it runs outside a browser).
export type SweepRow = {
  window: number; state: string; free_mib: number | null; prompt_tok_s: number | null; tok_s: number | null;
  line: string; slow?: boolean; error?: string; timed?: number;
};
export type Sweep = { windows: SweepRow[]; pick: number | null; why: string; done: boolean; loads: number };
export type SweepJob = { job: string; done: boolean; ok: boolean; line: string; lines: string[] };
export type TunerOffer = { tuner: string | null; line?: string; sends?: string; cost?: string; writes?: string; rounds?: number };
export type Setting = { key: string; value: string; why: string; server: Record<string, { set: string; revert: string; restart: string }> };
export type Note = { kind: string; by: string; by_line: string; text?: string; best_at?: string[]; avoid?: string[];
  settings?: Setting[]; dropped?: number };
export type SweepAnswer = { sweep: Sweep | null; job: SweepJob | null; offer: string; cli: string; use: string | null;
  tuner?: TunerOffer; tuner_job?: SweepJob | null; notes?: Record<string, Note> };

/** A figure as the host gave it; "unknown" where it did not tell, never a made-up number. */
export function fig(v: number | null | undefined, unit = ""): string {
  return typeof v === "number" ? `${v.toLocaleString("en-US")}${unit}` : "unknown";
}

/** The row's cells: window, on the card, free, prompt speed, reply speed, and the pick's mark. */
export function cells(r: SweepRow, pick: number | null): string[] {
  const measured = !r.error;
  return [
    r.window.toLocaleString("en-US"),
    r.error ? "did not load" : r.state,
    measured ? fig(r.free_mib, " MiB") : "not measured",
    measured ? fig(r.prompt_tok_s, " tok/s") : "not measured",
    measured ? fig(r.tok_s, " tok/s") + (r.timed === 2 ? " (timed twice)" : "") : "not measured",
    r.window === pick ? "the pick" : r.slow ? "past the cliff" : "",
  ];
}

export const HEAD = ["window", "on the card", "free", "prompt", "reply", ""];

export function running(a: SweepAnswer | null): boolean {
  return !!a?.job && !a.job.done;
}
