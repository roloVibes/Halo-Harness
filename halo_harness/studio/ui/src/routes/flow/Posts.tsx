// flow-posts: one row per post of the run (the project's posts.json): the
// platform chip, a grey DRY RUN badge or a red LIVE one, the text, the media
// count, the Postiz post id and the scheduled time; a failed post shows why.
import type { MotionState } from "../../lib/motion";
import { short } from "../orchestra/format";
import { Metric, NoFlow } from "./bits";
import { NONE, useFlow } from "./store";
import type { Post } from "./types";

export function PlatformChip({ p }: { p: string }) {
  return (
    <span className="og-chip mono fl-platform" data-platform={p}>
      {p}
    </span>
  );
}

export function LiveBadge({ dry }: { dry: boolean }) {
  return (
    <span className="badge fl-live-badge" data-live={!dry || undefined}>
      {dry ? "dry run" : "live"}
    </span>
  );
}

function when(s: string | null | undefined): string {
  if (!s) return "";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Row({ p, full }: { p: Post; full?: boolean }) {
  return (
    <li className="fl-post" data-error={p.error ? "true" : undefined} data-testid="flow-post">
      <div className="fl-post-head">
        <PlatformChip p={p.platform} />
        <LiveBadge dry={p.dry_run} />
        <span className="mono muted">{(p.media || []).length} media</span>
        <span className="spacer" />
        <span className="mono muted" title="Postiz post id">{p.post_id || (p.dry_run ? "no id (dry run)" : "-")}</span>
      </div>
      {p.title && <div className="fl-post-title">{p.title}</div>}
      <div className="fl-post-text">{full ? p.text : short(p.text, 120)}</div>
      {(p.scheduled_at || p.ts) && (
        <div className="mono muted fl-post-when">
          {p.scheduled_at ? `scheduled ${when(p.scheduled_at)}` : `logged ${when(p.ts)}`}
        </div>
      )}
      {p.error && <div className="md-error mono">{p.error}</div>}
    </li>
  );
}

export function PostsGlance() {
  const posts = useFlow((s) => s.data?.posts || NONE);
  const has = useFlow((s) => !!s.data);
  if (!has) return <NoFlow what="The posts" />;
  const live = posts.filter((p) => !p.dry_run).length;
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={posts.length} label="posts" />
        <Metric value={live} label={live ? "live on the platforms" : posts.length ? "live (all dry runs)" : "live"} tone={live ? "bad" : undefined} />
      </div>
      <ul className="fl-posts fl-posts-mini">
        {posts.slice(0, 4).map((p, i) => (
          <li key={i} className="fl-post-head" data-testid="flow-post">
            <PlatformChip p={p.platform} />
            <LiveBadge dry={p.dry_run} />
            <span className="fl-post-text">{short(p.text, 48)}</span>
          </li>
        ))}
      </ul>
      {!posts.length && <div className="og-wait muted">Confirm the render to move the run on to its posts, one per platform.</div>}
    </div>
  );
}

export function PostsDetail() {
  const posts = useFlow((s) => s.data?.posts || NONE);
  const has = useFlow((s) => !!s.data);
  if (!has) return <NoFlow what="The posts" />;
  const live = posts.filter((p) => !p.dry_run).length;
  return (
    <ul className="fl-posts">
      {posts.length > 0 && (
        <li className="glance-hint mono">
          {posts.length} post{posts.length === 1 ? "" : "s"} · {live ? `${live} live` : "all dry runs: nothing was sent"}
        </li>
      )}
      {posts.map((p, i) => (
        <Row key={i} p={p} full />
      ))}
      {!posts.length && <li className="og-wait muted">Confirm the render to move the run on to its posts (dry runs unless the post step says live: true).</li>}
    </ul>
  );
}

export function usePostsMotion(): MotionState {
  const state = useFlow((s) => s.data?.flow.steps.find((x) => x.kind === "post")?.state);
  const bad = useFlow((s) => (s.data?.posts || NONE).some((p) => p.error));
  const n = useFlow((s) => s.data?.posts.length || 0);
  if (state === "running") return "working";
  if (bad || state === "failed") return "error";
  return n ? "idle" : "none";
}
