// Problems' NOT CONNECTED block (3.3.16.3): every square block on the open lineup's board with no line from main -- its
// rule is `off`, so main never uses it -- one row each with the fix; a click selects the block (its When page says how
// to draw the line). A warning, not a block: the lineup still runs.
import { useMemo } from "react";
import { onBoard, select, useWf, wf } from "../workflows/store";
import { selectBlock } from "./blockState";

export function useUnconnected(): string[] {
  const board = useWf((s) => s.board);
  return useMemo(() => onBoard({ ...wf.get(), board }).filter((q) => q.when_mode === "off").map((q) => q.ref), [board]);
}

export function UnconnectedGroup({ refs }: { refs: string[] }) {
  if (!refs.length) return null;
  return (
    <section className="rp-group" data-sev="warns" data-testid="roles-problems-unconnected">
      <div className="rail-label mono">NOT CONNECTED · {refs.length}</div>
      <ul className="rp-list">
        {refs.map((ref) => (
          <li key={ref}>
            <button className="rp-row" data-sev="warn" data-block={ref} data-testid="roles-problem-block" title="Select the block: its When page draws the line"
                    onClick={() => (selectBlock(ref), select(ref, "when"))}>
              <span className="rp-dot" aria-hidden="true" />
              <span className="rp-text">{ref} is not connected: main never uses it</span>
              <span className="rp-fix muted">fix: draw its line from main (its When page, or the block's menu: Connect to main), or take it off</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
