// The plan's cost forecast (3.1.2.0 R2; orchestra/forecast.py answers it in the plan payload and in
// each PUT): a lane's cost chip and the header's total against the goal's budget_usd, money written
// as work/forecast.py's `money` writes it.
import type { Forecast, ForecastLine, ForecastTotal } from "./types";

/** Dollars: two decimals from a dollar up, else two to four ($0.50, $0.105, $0.0306); $0; ? unknown. */
export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "?";
  if (!v) return "$0";
  if (v >= 1) return `$${v.toFixed(2)}`;
  const [whole, dec = ""] = v.toFixed(4).split(".");
  return `$${whole}.${dec.replace(/0+$/, "").padEnd(2, "0")}`;
}

/** A lane's chip: its low-high band, or "? $" when its model has no catalog price. */
export function costText(x: ForecastLine | undefined): string {
  if (!x) return "";
  if (!x.priced) return "? $";
  return x.usd_low === x.usd_high ? money(x.usd) : `${money(x.usd_low)}-${money(x.usd_high)}`;
}

export function costTitle(x: ForecastLine): string {
  const from = x.source === "lead" ? "the lead's estimate" : "the heuristic (goal size and claimed files)";
  if (!x.priced) return `${x.model || "no model"} has no catalog price: ${x.tokens_in} in / ${x.tokens_out} out tokens from ${from}`;
  return `${x.tokens_in} in / ${x.tokens_out} out tokens from ${from}, at ${x.model}'s catalog price`;
}

/** The header's line: the band, the unpriced lanes, the budget. */
export function totalText(t: ForecastTotal): string {
  const band = `forecast ${money(t.usd_low)}-${money(t.usd_high)}${t.unpriced ? ` (+${t.unpriced} unpriced)` : ""}`;
  if (t.budget_usd === null || t.budget_usd === undefined) return `${band} · no budget`;
  return `${band} of ${money(t.budget_usd)}${t.over ? " · over budget" : ""}`;
}

export function byJob(f: Forecast | null): Record<string, ForecastLine> {
  return Object.fromEntries((f?.lanes || []).map((x) => [x.job, x]));
}
