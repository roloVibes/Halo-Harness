// The pieces a Start view is made of (3.1.4.0 R2, from Fleet's Start view; 3.3.16.0 R2 "the Fleet fold": that view
// went with the section; its five unread Machines lines went in P4 batch 12): numbered lines, "try it" and
// "open the workspace anyway". Session's Start view reads them too.
import type { ReactNode } from "react";

/** A Start view's numbered lines. */
export function Explain({ lines }: { lines: string[] }) {
  return (
    <ol className="fl-explain">
      {lines.map((line, i) => (
        <li key={line}>
          <span className="fl-explain-n mono">{i + 1}</span>
          <span>{line}</span>
        </li>
      ))}
    </ol>
  );
}

/** "Start a session in a terminal, it appears here." and how. */
export function TryIt({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="fs-try">
      <b>{title}</b>
      <span className="muted">{children}</span>
    </div>
  );
}

export function OpenAnyway({ onOpen, testid }: { onOpen: () => void; testid: string }) {
  return (
    <button className="og-link mono" onClick={onOpen} data-testid={testid}>
      open the workspace anyway
    </button>
  );
}
