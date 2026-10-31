// 3.3.7.0 R4: the Steward page's refresh lines -- the off-hours refresh's plan ("next: ..., tonight 22:00+"), its
// last run ("last refresh: qwen3-coder:30b on pc: battery + bench in 251 s, profile and speed card verified by the
// host") and the last roster review (GET local/refresh, studio/local_guard_api.py; host/refresh.py).
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type Refresh = { line: string; last_line: string; review: { lines?: string[] } | null };

export function StewardRefresh() {
  const [got, setGot] = useState<Refresh | null>(null);
  useEffect(() => {
    let live = true;
    api.get<Refresh>("local/refresh")
      .then((r) => {
        if (live) setGot(r);
      })
      .catch(() => {
        if (live) setGot(null);
      });
    return () => {
      live = false;
    };
  }, []);
  if (!got) return null;
  const review = got.review?.lines?.[0] || "";
  return (
    <section className="lc-block" aria-label="The off-hours refresh" data-testid="local-steward-refresh">
      <div className="rail-label mono">THE OFF-HOURS REFRESH</div>
      <div className="mono muted lc-status">
        <div data-testid="local-steward-refresh-next">{got.line}</div>
        <div data-testid="local-steward-refresh-last">{got.last_line}</div>
        {review && <div data-testid="local-steward-review">roster review: {review}</div>}
      </div>
    </section>
  );
}
