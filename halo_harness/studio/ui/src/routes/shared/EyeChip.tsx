// The eye chip (3.3.6.0 R6, rolo: "we need to also identify if models have the ability to see images so we know
// which ones to load before sharing a screenshot with it"): "sees", "no eyes" or "eyes?" on every model row --
// Local's Library, Models and Loaded now, the model picker, Setup's Default model, Settings' model row (all
// through CardChips) -- with the truth as its mark (✓ verified by the battery's image probe, ◇ declared by the
// server or the catalog, ≈ expected from the family) and the source in its title (providers/vision_fact.py).
import type { CardView } from "./ModelCard";

export type EyeFact = { value: boolean | null | undefined; truth?: string | null; source?: string | null };

const GLYPH: Record<string, string> = { verified: "✓", declared: "◇", expected: "≈" };
const TRUTH: Record<string, string> = {
  verified: "verified: the battery's image probe ran on this host",
  declared: "declared: the server or the catalog says so (not probed)",
  expected: "expected: its family usually sees (not probed)",
};

/** The vision fact a card carries. */
export function eyeOf(card?: Pick<CardView, "vision" | "vision_truth" | "sources"> | null): EyeFact {
  return { value: card?.vision, truth: card?.vision_truth, source: card?.sources?.vision };
}

export function eyeWord(f: EyeFact): string {
  return f.value === true ? "sees" : f.value === false ? "no eyes" : "eyes?";
}

export function eyeTitle(f: EyeFact): string {
  const what = f.value === true ? "Reads images" : f.value === false ? "Cannot see images" : "Nothing says whether it reads images";
  const why = f.truth ? TRUTH[f.truth] || f.truth : "a probe settles it (halo models probe <ref>, or Probe on its row)";
  return `${what} -- ${why}${f.source ? ` (${f.source})` : ""}`;
}

export function EyeChip({ fact, testid = "eye-chip" }: { fact: EyeFact; testid?: string }) {
  const state = fact.value === true ? "sees" : fact.value === false ? "no" : "unknown";
  return (
    <span className="og-chip mono mcard-chip mcard-eye" data-testid={testid} data-eye={state} data-truth={fact.truth || "none"}
          title={eyeTitle(fact)}>
      {eyeWord(fact)}
      {fact.truth && <span className="mcard-eye-mark" aria-label={fact.truth}> {GLYPH[fact.truth] || ""}</span>}
    </span>
  );
}
