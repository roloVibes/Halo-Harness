// flow-metrics: per post and platform, the latest numbers Postiz reported
// (views, likes, comments, shares when present) and a small sparkline over
// the run's metrics tail. Dry-run posts have none: the empty state says so.
// `totals()` reads a raw analytics answer the way flows/postiz_parse.py
// does: `{label, data: [{total}]}` series (the last point) or a plain map.
import type { MotionState } from "../../lib/motion";
import { Metric, NoFlow } from "./bits";
import { PlatformChip } from "./Posts";
import { NONE, useFlow } from "./store";
import type { MetricRow } from "./types";

const KEYS = ["views", "likes", "comments", "shares"] as const;
const LABELS: Record<string, string> = {};
for (const [k, names] of Object.entries({
  views: ["views", "view", "impressions", "impression", "plays", "play", "video_views", "views_count"],
  likes: ["likes", "like", "favorites", "favourites", "like_count"],
  comments: ["comments", "comment", "replies", "reply", "comment_count"],
  shares: ["shares", "share", "retweets", "reposts", "repost", "shares_count"],
}))
  for (const n of names) LABELS[n] = k;

function num(v: unknown): number | null {
  if (typeof v === "number" && isFinite(v)) return v;
  if (typeof v === "string" && /^\s*-?\d+(\.\d+)?\s*$/.test(v)) return Number(v);
  return null;
}

export function totals(raw: unknown): Record<string, number> {
  const out: Record<string, number> = {};
  const add = (label: unknown, v: number | null) => {
    const key = LABELS[String(label).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")];
    if (key && v !== null) out[key] = (out[key] || 0) + v;
  };
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") {
      const d = node as Record<string, unknown>;
      if ("label" in d && ("data" in d || "total" in d || "value" in d)) {
        const pts = Array.isArray(d.data) ? d.data : null;
        const last = pts && pts.length ? pts[pts.length - 1] : null;
        const lv = last && typeof last === "object" ? (last as Record<string, unknown>) : null;
        add(d.label, lv ? num(lv.total ?? lv.value ?? lv.count) : last !== null ? num(last) : num(d.total ?? d.value));
        return;
      }
      for (const [k, v] of Object.entries(d)) {
        if (num(v) !== null && typeof v !== "boolean") add(k, num(v));
        else if (v && typeof v === "object") walk(v);
      }
    }
  };
  walk(raw);
  return out;
}

type Series = { key: string; platform: string; post: string; samples: { ts: number; t: Record<string, number> }[] };

function series(rows: MetricRow[]): Series[] {
  const by = new Map<string, Series>();
  for (const r of rows) {
    if (!r.metrics) continue;
    const key = `${r.platform}:${r.post_id || ""}`;
    const s = by.get(key) || { key, platform: r.platform, post: String(r.post_id || ""), samples: [] };
    s.samples.push({ ts: typeof r.ts === "number" ? r.ts : Date.parse(String(r.ts)) / 1000 || 0, t: totals(r.metrics) });
    by.set(key, s);
  }
  return [...by.values()].map((s) => ({ ...s, samples: s.samples.sort((a, b) => a.ts - b.ts) }));
}

export function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return <svg className="fl-spark" viewBox="0 0 80 20" aria-hidden="true" />;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * 78 + 1).toFixed(1)},${(19 - ((v - lo) / (hi - lo || 1)) * 18).toFixed(1)}`).join(" ");
  return (
    <svg className="fl-spark" viewBox="0 0 80 20" role="img" aria-label={`trend ${values.join(", ")}`}>
      <polyline points={pts} />
    </svg>
  );
}

function useSeries(): Series[] {
  const rows = useFlow((s) => s.data?.metrics_tail || NONE);
  return series(rows);
}

function Empty() {
  const posts = useFlow((s) => s.data?.posts || NONE);
  const dry = !posts.length || posts.every((p) => p.dry_run);
  return <div className="og-wait muted" data-testid="metrics-empty">{dry ? "dry run: no metrics yet -- set live: true on the post step to post and measure." : "Wait for the measure step's next sample (every few hours)."}</div>;
}

export function MetricsGlance() {
  const has = useFlow((s) => !!s.data);
  const ss = useSeries();
  if (!has) return <NoFlow what="The metrics" />;
  if (!ss.length) return <Empty />;
  const sum = (k: string) => ss.reduce((m, s) => m + (s.samples[s.samples.length - 1].t[k] || 0), 0);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={sum("views")} label="views" tone="accent" />
        <Metric value={sum("likes")} label="likes" />
      </div>
      <div className="glance-hint mono">
        {ss.length} post{ss.length === 1 ? "" : "s"} · {sum("comments")} comments · {sum("shares")} shares
      </div>
    </div>
  );
}

export function MetricsDetail() {
  const has = useFlow((s) => !!s.data);
  const ss = useSeries();
  if (!has) return <NoFlow what="The metrics" />;
  if (!ss.length) return <Empty />;
  return (
    <div className="fl-table-wrap">
      <table className="fl-table mono">
      <thead>
        <tr>
          <th>post</th>
          {KEYS.map((k) => <th key={k}>{k}</th>)}
          <th>trend</th>
        </tr>
      </thead>
      <tbody>
        {ss.map((s) => {
          const last = s.samples[s.samples.length - 1].t;
          const lead = KEYS.find((k) => k in last) || "views";
          return (
            <tr key={s.key}>
              <td><PlatformChip p={s.platform} /> <span className="muted">{s.post.slice(0, 10)}</span></td>
              {KEYS.map((k) => <td key={k}>{k in last ? last[k] : "-"}</td>)}
              <td title={`${lead}, ${s.samples.length} samples`}><Spark values={s.samples.map((x) => x.t[lead] || 0)} /></td>
            </tr>
          );
        })}
      </tbody>
    </table>
      </div>
  );
}

export function useMetricsMotion(): MotionState {
  const state = useFlow((s) => s.data?.flow.steps.find((x) => x.kind === "metrics")?.state);
  const n = useFlow((s) => s.data?.metrics_tail.length || 0);
  if (state === "running") return "working";
  return n ? "idle" : "none";
}
