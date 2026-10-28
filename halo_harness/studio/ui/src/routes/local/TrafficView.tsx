// Local's traffic view (3.3.5.0 R1), the Live display's cousin: every call to
// every local server as it happens -- the ledger as a stream, newest at the foot
// -- with the steward's server events inline as muted rows, a sparkline per host
// above (calls per minute, trims and cuts marked, the bytes in and out per
// minute), filters (host, model, machine, kind) and Follow like Live: it keeps
// the newest row in view; scrolling up pauses it and a pill counts what came
// since. The catch-up is GET local/traffic?since=15m; each `traffic` frame adds
// its rows (studio/local_traffic.py, deduped by the line's id).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Button, Icon } from "../../lib/ui";
import { loadTraffic, useLocal } from "./store";
import { EventRow, TrafficRow } from "./TrafficRow";
import { TrafficSpark } from "./TrafficSpark";
import type { TRow } from "./types";

type Filters = { host: string; model: string; from: string; kind: string };
const KINDS = ["turn", "compaction", "small", "repair", "calibrate"];

function Pick({ value, onChange, all, options, label, testid }: { value: string; onChange: (v: string) => void; all: string; options: string[]; label: string; testid: string }) {
  return (
    <label className="fac-pick" title={label}>
      <select value={value} aria-label={label} onChange={(e) => onChange(e.target.value)} data-testid={testid}>
        <option value="">{all}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function keep(r: TRow, f: Filters): boolean {
  if (f.host && r.host !== f.host) return false;
  if (r.type === "event") return !f.model || r.model === f.model;
  if (f.model && r.model !== f.model) return false;
  if (f.from && (r.from || "this machine") !== f.from) return false;
  return !f.kind || r.kind === f.kind;
}

export function TrafficView() {
  const rows = useLocal((s) => s.rows);
  const spark = useLocal((s) => s.spark);
  const [f, setF] = useState<Filters>({ host: "", model: "", from: "", kind: "" });
  const [follow, setFollow] = useState(true);
  const [seenAt, setSeenAt] = useState(0);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    void loadTraffic();
  }, []);
  const opts = useMemo(() => {
    const calls = rows.filter((r) => r.type === "call");
    const uniq = (xs: (string | null | undefined)[]) => [...new Set(xs.filter(Boolean) as string[])].sort();
    return { hosts: uniq(rows.map((r) => r.host)), models: uniq(calls.map((r) => r.model)), from: uniq(calls.map((r) => r.from || "this machine")) };
  }, [rows]);
  const shown = useMemo(() => rows.filter((r) => keep(r, f)), [rows, f]);
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && follow) {
      el.scrollTop = el.scrollHeight;
      setSeenAt(shown.length);
    }
  }, [shown, follow]);
  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (bottom !== follow) setFollow(bottom);
  };
  const set = (k: keyof Filters) => (v: string) => setF((x) => ({ ...x, [k]: v }));
  const fresh = follow ? 0 : Math.max(0, shown.length - seenAt);
  const hosts = Object.keys(spark).filter((h) => !f.host || h === f.host).sort();
  return (
    <section className="lc-block lc-traffic" aria-label="Traffic" data-testid="local-traffic" data-follow={follow || undefined} data-rows={shown.length}>
      <div className="lc-head">
        <span className="rail-label mono">TRAFFIC · EVERY CALL TO A LOCAL SERVER, LIVE</span>
        <span className="spacer" />
        <Pick value={f.host} onChange={set("host")} all="every host" options={opts.hosts} label="host" testid="local-traffic-host" />
        <Pick value={f.model} onChange={set("model")} all="every model" options={opts.models} label="model" testid="local-traffic-model-pick" />
        <Pick value={f.from} onChange={set("from")} all="every machine" options={opts.from} label="the machine that called" testid="local-traffic-from" />
        <Pick value={f.kind} onChange={set("kind")} all="every kind" options={KINDS} label="kind" testid="local-traffic-kind" />
        <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} data-testid="local-traffic-follow"
                onClick={() => setFollow((x) => !x)} title="Keep the newest row in view; scrolling up pauses it">
          Follow
        </Button>
      </div>
      {hosts.length > 0 && (
        <div className="lc-tsparks">
          {hosts.map((h) => <TrafficSpark key={h} host={h} buckets={spark[h]} />)}
        </div>
      )}
      <div className="lc-tlist" ref={scroller} onScroll={onScroll} data-testid="local-traffic-list">
        {shown.length ? (
          <ul>
            {shown.map((r) => (r.type === "event" ? <EventRow key={r.id} r={r} /> : <TrafficRow key={r.id} r={r} />))}
          </ul>
        ) : (
          <p className="muted lc-empty" data-testid="local-traffic-empty">No call to a local server in the last 15 minutes: the rows come as halos call one.</p>
        )}
      </div>
      {fresh > 0 && (
        <button type="button" className="lc-new mono" data-testid="local-traffic-new" onClick={() => setFollow(true)}>
          {fresh} new row{fresh === 1 ? "" : "s"} · follow
        </button>
      )}
    </section>
  );
}
