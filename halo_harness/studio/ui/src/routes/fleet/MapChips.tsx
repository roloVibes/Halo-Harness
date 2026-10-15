// The capability chips on a harness box of the map (3.0.6.0 R6): at most
// three, from its catalog (caps.ts: the owner's tags first, then the GPU,
// the OS, its craft apps), right-aligned in the box head. `chipsWidth` is
// what they take, so the head's sub line shortens to fit beside them.
import { useMemo } from "react";
import { useCaps } from "./caps";

const CHAR_W = 6.1;
const PAD_X = 6;
const GAP = 4;

const chipW = (t: string) => Math.round(t.length * CHAR_W + 2 * PAD_X);

export function useBoxChips(): { chips: Map<string, string[]>; focus: string } {
  const rows = useCaps((s) => s.rows);
  const focus = useCaps((s) => s.focus);
  const chips = useMemo(() => new Map((rows || []).map((r) => [r.harness, (r.chips || []).slice(0, 3).map((c) => c.slice(0, 14))])), [rows]);
  return { chips, focus };
}

export function chipsWidth(chips: string[]): number {
  return chips.length ? chips.reduce((n, c) => n + chipW(c) + GAP, 0) : 0;
}

/** The chips, right edge at `right`, centred on the head's line at `cy`. */
export function BoxChips({ chips, right, cy }: { chips: string[]; right: number; cy: number }) {
  let x = right - chipsWidth(chips) + GAP;
  const out = chips.map((c) => {
    const w = chipW(c);
    const at = x;
    x += w + GAP;
    return (
      <g key={c} className="fm-chip" data-testid="fleet-box-chip">
        <rect x={at} y={cy - 8} width={w} height={16} rx={8} />
        <text x={at + w / 2} y={cy + 3.5} textAnchor="middle">{c}</text>
      </g>
    );
  });
  return <g className="fm-chips">{out}</g>;
}
