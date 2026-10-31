// 3.3.7.0 R4: the Hosts card's guard lines -- what holds the card that no halo explains ("foreign: 1 model, 17.3 GB,
// since 14:02", ollama_steward/idle.py), whether it is idle, and the off-hours refresh's plan and last run ("next:
// qwen3-coder:30b ..., tonight 22:00+"; "last refresh: ... verified by the host"), GET local/idle?host=<name>
// (studio/local_guard_api.py: through the halo host that serves it, else this machine's reads). Read when the card
// shows and when what is loaded on it changes. ForeignLines is the traffic view's form: every host's foreign line.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export type GuardRow = { host: string; line: string; busy: string; idle_s: number | null; foreign_line: string;
  refresh_line: string; last_line: string; via: string };
type Guards = { hosts: GuardRow[] };

function useGuards(host: string, key: string): GuardRow[] | null {
  const [got, setGot] = useState<GuardRow[] | null>(null);
  useEffect(() => {
    let live = true;
    api.get<Guards>("local/idle", host ? { host } : undefined)
      .then((r) => {
        if (live) setGot(r.hosts || null);
      })
      .catch(() => {
        if (live) setGot(null);
      });
    return () => {
      live = false;
    };
  }, [host, key]);
  return got;
}

export function HostGuards({ name, loadedKey }: { name: string; loadedKey: string }) {
  const rows = useGuards(name, loadedKey);
  const g = rows?.find((r) => r.host === name);
  if (!g) return null;
  return (
    <div className="lc-guards" data-testid="local-host-guards" data-via={g.via} data-busy={g.busy ? "yes" : "no"}>
      {g.foreign_line && (
        <div className="mono lc-host-line lc-foreign" data-testid="local-host-foreign"
             title="a model in /api/ps that no halo call, load, battery or bench explains: the bench and the refresh wait for it">
          {g.foreign_line}
        </div>
      )}
      <div className="mono muted lc-host-line" data-testid="local-host-idle">{g.line}</div>
      {g.refresh_line && <div className="mono muted lc-host-line" data-testid="local-host-refresh"
                              title="halo host refresh status | now | off">refresh: {g.refresh_line}</div>}
      {g.last_line && <div className="mono muted lc-host-line" data-testid="local-host-refresh-last">{g.last_line}</div>}
    </div>
  );
}

export function ForeignLines({ refreshKey }: { refreshKey: number }) {
  const rows = useGuards("", String(refreshKey));
  const shown = (rows || []).filter((r) => r.foreign_line);
  if (!shown.length) return null;
  return (
    <div className="lc-foreign-list" data-testid="local-traffic-foreign">
      {shown.map((r) => (
        <div key={r.host} className="mono lc-foreign" data-testid="local-traffic-foreign-row" data-host={r.host}>
          {r.host}: {r.foreign_line}
        </div>
      ))}
    </div>
  );
}
