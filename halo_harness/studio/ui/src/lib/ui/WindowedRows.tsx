// A long list drawn in full, a window at a time (3.3.5.0 R0 (f): every model
// list shows every model). Up to WINDOW_AT rows render at once; past that the
// first WINDOW_AT render now and the rest follow, CHUNK rows per frame, so a
// provider with thousands of models never holds the page. Each chunk skips its
// own layout and paint while it is off screen (`content-visibility: auto`), so
// every row is in the page (search, Ctrl+F and the tests find it) at the cost
// of the rows on screen only.
import { useEffect, useState, type ReactNode } from "react";

export const WINDOW_AT = 200;
const CHUNK = 100;

export function WindowedRows<T>({ items, render, testid }: { items: T[]; render: (item: T, i: number) => ReactNode; testid?: string }) {
  const first = Math.min(items.length, WINDOW_AT);
  const [shown, setShown] = useState(first);
  useEffect(() => {
    setShown(Math.min(items.length, WINDOW_AT));
  }, [items]);
  useEffect(() => {
    if (shown >= items.length) {
      return undefined;
    }
    const id = window.requestAnimationFrame(() => setShown((n) => Math.min(items.length, n + CHUNK)));
    return () => {
      window.cancelAnimationFrame(id);
    };
  }, [shown, items]);
  const upto = Math.min(shown, items.length);
  if (items.length <= WINDOW_AT) return <>{items.map((it, i) => render(it, i))}</>;
  const chunks: ReactNode[] = [];
  for (let at = 0; at < upto; at += CHUNK) {
    const part = items.slice(at, Math.min(upto, at + CHUNK));
    chunks.push(
      <div key={at} className="wrows-chunk" data-testid={testid}>
        {part.map((it, j) => render(it, at + j))}
      </div>,
    );
  }
  return <>{chunks}</>;
}
