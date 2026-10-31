// 3.3.7.0 R3 (G5): the loading tax beside the dollars on the session's Cost panel -- how many loads the session paid
// and the seconds they took (GET local/loads?session=<id>, local_sched/loads.py: the ledger's calls that paid a load,
// plus the scheduler's own pivots and warms). Local cost is time, so the figure is seconds. Read again every 30 s
// while the page shows; nothing shows before the session's first load.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type Tax = { count: number; seconds: number; line: string; per_model: Record<string, { count: number; seconds: number }> };
const POLL_MS = 30_000;

export function secs(s: number): string {
  const n = Math.max(0, Math.round(s));
  return n < 60 ? `${n} s` : `${Math.floor(n / 60)} m ${String(n % 60).padStart(2, "0")} s`;
}

export function LoadingTax({ sid }: { sid: string | null | undefined }) {
  const [got, setGot] = useState<Tax | null>(null);
  useEffect(() => {
    if (!sid) {
      setGot(null);
      return;
    }
    let live = true;
    const load = async () => {
      try {
        const r = await api.get<Tax>("local/loads", { session: sid });
        if (live) setGot(r);
      } catch {
        if (live) setGot(null);
      }
    };
    void load();
    const id = window.setInterval(() => {
      if (!document.hidden) void load();
    }, POLL_MS);
    return () => {
      live = false;
      window.clearInterval(id);
    };
  }, [sid]);
  if (!got || !got.count) return null;
  const per = Object.entries(got.per_model || {}).map(([m, v]) => `${m}: ${v.count} load${v.count === 1 ? "" : "s"}, ${secs(v.seconds)}`);
  return (
    <div className="sco-fig" title={[got.line, ...per].join("\n")}>
      <span className="sco-label mono">LOADING</span>
      <b className="sco-value mono" data-testid="session-cost-loading">{`${got.count} · ${secs(got.seconds)}`}</b>
    </div>
  );
}
