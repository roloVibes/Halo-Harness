// The model picker's rows (3.4.1.3 "Pick, don't type"): what one search box matches, how the catalog groups by
// provider, which rows a field's needs dim, and the flat order the keyboard walks. Pure: no React, no store.
import type { ModelRow, ModelsStatus } from "../../roles/types";

export type Sort = "name" | "price" | "context" | "best";
export type Group = { provider: string; label: string; state: string; ok: boolean; rows: ModelRow[] };

/** The words a row answers to: its ref, provider, name, price, context, what it takes, its best-at line and kinds,
 *  its card's chips, "local" or "cloud", "cheap" under $1 in per 1M, "free" at $0, and the window ("200k"). */
export function wordsOf(m: ModelRow, kinds: string[], extra = ""): string {
  const cheap = typeof m.price_in === "number" && m.price_in < 1 ? "cheap" : "";
  const free = m.price_in === 0 ? "free" : "";
  return [m.ref, m.provider, m.group, m.detail, m.price, m.context, m.chips, m.best_at?.line, ...kinds, ...(m.takes || []),
    ...Object.values(m.card?.chips || {}), m.fit?.level || "", m.local ? "local" : "cloud", cheap, free, m.effort_word || "", extra]
    .join(" ").toLowerCase();
}

/** Does the row state every need? `tools` and `think` read the row's own flags too. */
export function fits(m: ModelRow, needs: string[]): boolean {
  const takes = m.takes || [];
  return needs.every((n) => takes.includes(n) || (n === "tools" && m.tools === true) || (n === "think" && !!m.reasoning)
    || (n === "reasoning" && (!!m.reasoning || takes.includes("think"))));
}

const PROVIDER_WORD: Record<string, string> = { openrouter: "OpenRouter", databricks: "Databricks", anthropic: "Anthropic", openai: "OpenAI",
  ollama: "Ollama", huggingface: "Hugging Face", experiential: "Experiential Labs", copilot: "Copilot" };

/** One line of a provider's state: "signed in · 63 models", "listing failed: ...", from GET models/status. */
export function providerState(name: string, count: number, st: ModelsStatus | null): { label: string; state: string; ok: boolean } {
  const p = st?.providers.find((x) => x.name === name);
  const looked = (st?.looked_at || []).filter((l) => l.name === name);
  const failed = looked.find((l) => !l.ok);
  const label = p?.label || PROVIDER_WORD[name] || name || "other";
  if (failed && !count) return { label, state: failed.line, ok: false };
  const word = name === "ollama" || name === "huggingface" ? "reachable" : "signed in";
  return { label, state: `${word} · ${count} model${count === 1 ? "" : "s"}${failed ? ` · ${failed.label}: ${failed.line}` : ""}`, ok: true };
}

/** The providers with no row here and why (one line each), for the line under the groups. */
export function notHere(groups: Group[], st: ModelsStatus | null): { unset: string[]; failing: { label: string; line: string }[] } {
  const have = new Set(groups.map((g) => g.provider));
  const looked = (st?.looked_at || []).filter((l) => !l.ok && !have.has(l.name));
  return {
    unset: looked.filter((l) => l.line.startsWith("not configured")).map((l) => l.label),
    failing: looked.filter((l) => !l.line.startsWith("not configured")).map((l) => ({ label: l.label, line: l.line })),
  };
}

export function sortRows(rows: ModelRow[], sort: Sort, kindsOf: (m: ModelRow) => string[]): ModelRow[] {
  const by: Record<Sort, (a: ModelRow, b: ModelRow) => number> = {
    name: (a, b) => a.ref.localeCompare(b.ref),
    price: (a, b) => (a.price_in ?? 1e9) - (b.price_in ?? 1e9) || a.ref.localeCompare(b.ref),
    context: (a, b) => (b.context_tokens ?? 0) - (a.context_tokens ?? 0) || a.ref.localeCompare(b.ref),
    best: (a, b) => kindsOf(b).length - kindsOf(a).length || a.ref.localeCompare(b.ref),
  };
  return [...rows].sort(by[sort]);
}

/** The searched rows grouped by provider (the provider of the picked value first, then by label), each group sorted,
 *  the rows that fit the needs first inside it; sorted by price, context or best, one list across the providers. */
export function groupRows(models: ModelRow[], q: string, sort: Sort, needs: string[], st: ModelsStatus | null,
  kindsOf: (m: ModelRow) => string[], value: string, extra: (m: ModelRow) => string = () => ""): Group[] {
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const hit = models.filter((m) => words.every((w) => wordsOf(m, kindsOf(m), extra(m)).includes(w)));
  const by = new Map<string, ModelRow[]>();
  for (const m of hit) by.set(m.provider || "other", [...(by.get(m.provider || "other") || []), m]);
  const counts = new Map<string, number>();
  for (const m of models) counts.set(m.provider || "other", (counts.get(m.provider || "other") || 0) + 1);
  if (sort !== "name") { // a price, context or best sort ranks across every provider: one list
    const sorted = sortRows(hit, sort, kindsOf);
    const rows = needs.length ? [...sorted.filter((m) => fits(m, needs)), ...sorted.filter((m) => !fits(m, needs))] : sorted;
    return rows.length ? [{ provider: "all", label: "every provider", state: `sorted by ${sort}`, ok: true, rows }] : [];
  }
  const first = models.find((m) => m.ref === value)?.provider || "";
  const groups = [...by.entries()].map(([provider, list]): Group => {
    const sorted = sortRows(list, sort, kindsOf);
    const rows = needs.length ? [...sorted.filter((m) => fits(m, needs)), ...sorted.filter((m) => !fits(m, needs))] : sorted;
    return { provider, ...providerState(provider, counts.get(provider) || 0, st), rows };
  });
  return groups.sort((a, b) => Number(b.provider === first) - Number(a.provider === first) || a.label.localeCompare(b.label));
}

/** The refs a known prefix may start with; a typed ref with another prefix is caught before it is asked about. */
export const PREFIXES = ["or:", "dbx:", "ant:", "oai:", "ol:", "hf:", "xp:", "cp:", "local:"];
