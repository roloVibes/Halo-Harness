// 3.3.7.0 R2 (G15): the Session header's offline-promise chip -- "100 % local -- 0 tokens left this machine", or
// which calls left it and to where (GET local/offline?session=<id>, agent/offline_promise.py: the session log's
// calls and the traffic ledger's hosts). Its title lists each local call with the host it went to. Read again every
// 30 s while the page shows; nothing shows before the session's first call.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type Promise_ = { line: string; calls: number; left: number; per_call: string[] };
const POLL_MS = 30_000;

export function OfflineChip({ sid }: { sid: string | null | undefined }) {
  const [got, setGot] = useState<Promise_ | null>(null);
  useEffect(() => {
    if (!sid) {
      setGot(null);
      return;
    }
    let live = true;
    const load = async () => {
      try {
        const r = await api.get<Promise_>("local/offline", { session: sid });
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
  if (!got || !got.calls) return null;
  return (
    <span className="og-chip mono" data-testid="session-offline" data-left={got.left}
          title={["Offline promise (the session log and the traffic ledger)", ...got.per_call.slice(-12)].join("\n")}>
      {got.line}
    </span>
  );
}
