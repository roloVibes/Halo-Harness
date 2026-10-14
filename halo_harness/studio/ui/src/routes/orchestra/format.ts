// Small formatters the Orchestra panels share: elapsed time, clock time,
// cost, a short sha, and the report as text (the CLI's `format_report`).
import type { Report } from "./types";

/** `+4.2s`, `+1m05s`, `+1h02m`. */
export function elapsed(s: number | null | undefined): string {
  const v = Math.max(0, Number(s) || 0);
  if (v < 60) return `+${v.toFixed(1)}s`;
  if (v < 3600) return `+${Math.floor(v / 60)}m${String(Math.floor(v % 60)).padStart(2, "0")}s`;
  return `+${Math.floor(v / 3600)}h${String(Math.floor((v % 3600) / 60)).padStart(2, "0")}m`;
}

/** `14:02:09` for an epoch in seconds. */
export function clock(ts: number | null | undefined): string {
  if (!ts) return "--:--:--";
  return new Date(ts * 1000).toTimeString().slice(0, 8);
}

/** Elapsed or clock time, as the panel's option says. */
export function when(mode: "relative" | "absolute", elapsedS: number, ts: number): string {
  return mode === "absolute" ? clock(ts) : elapsed(elapsedS);
}

export function cost(usd: number | null | undefined): string {
  const v = Number(usd) || 0;
  return v >= 1 ? `$${v.toFixed(2)}` : `$${v.toFixed(4)}`;
}

export function sha(s: string | null | undefined): string {
  return s ? s.slice(0, 10) : "-";
}

export function short(text: string | null | undefined, n: number): string {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

export const CHECK_LABEL: Record<string, string> = {
  reviewer_fresh: "Every judge was a fresh session",
  reviewer_applied_by_code_tests_pass: "Judged answers applied by code, tests pass",
  no_piece_over_cap: "No piece sent back past the cap",
  all_branches_merged: "Every worker branch merged",
  record_equals_disk: "The record equals the disk",
  every_edit_streamed: "Every edit streamed: claimed, writing, written, released",
  tests_pass_finished_branch: "Tests pass on the finished branch",
  goal_done_when: "DONE WHEN",
};

/** The report as plain text, for Copy (the same lines `halo orchestra report` prints). */
export function reportText(r: Report): string {
  const mark = (ok: boolean | null) => (ok === true ? "PASS" : ok === false ? "FAIL" : "    ");
  const lines = [`run ${r.run_id}: ${r.status}${r.stop_reason ? ` -- ${r.stop_reason}` : ""}`];
  if (r.finished) lines.push(`  finished branch ${r.branch} at ${r.finished.slice(0, 12)}`);
  lines.push(`  tests ${r.tests_ok ? "pass" : "do not pass"}; cost ${cost(r.cost_usd)}; ${(r.elapsed_s || 0).toFixed(1)}s`);
  for (const l of r.lanes || []) lines.push(`  lane ${String(l.lane).padEnd(3)} ${l.state.padEnd(9)} returned ${l.pieces_returned}  ${cost(l.cost_usd)}  ${l.title}`);
  lines.push("  checks:");
  for (const c of r.checks || []) lines.push(`    ${mark(c.ok)}  ${c.id.padEnd(36)} ${c.detail || ""}`);
  return lines.join("\n");
}
