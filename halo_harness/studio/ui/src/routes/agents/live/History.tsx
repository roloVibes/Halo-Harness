// Live's History button and drawer (3.3.18.0 "The living canvas"; historyStore.ts holds the rows). The button sits on Live's
// bar with the count; the drawer is closed on load, opens on its click, closes on its x, Esc or the button again. A row
// opens that past thing as a replay on the canvas (replay.ts), the drawer closing behind it. 3.4.0.0 D: a goal run's row
// opens its report as a page of the drawer instead (run/RunReport.tsx), Replay and Back on it.
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { cost, short } from "../../orchestra/format";
import { history, loadHistory, openReport, toggleHistory, useHistory, type HistoryRow } from "./historyStore";
import { RunReport } from "../run/RunReport";
import { openLiveReplay, useLiveReplay } from "./replay";
import { took } from "./GroupBox";

const KIND: Record<string, string> = { session: "session", run: "goal run", mission: "mission" };

/** "3 min ago", "2 h ago", "Nov 8" for an epoch in seconds. */
export function ago(ts: number | null, now = Date.now()): string {
  if (!ts) return "when unknown";
  const s = Math.max(0, now / 1000 - ts);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function HistoryButton() {
  const n = useHistory((s) => s.rows.length);
  const open = useHistory((s) => s.open);
  useEffect(() => void loadHistory(), []);
  return (
    <Button size="sm" variant="ghost" className={open ? "on" : ""} aria-pressed={open} onClick={() => toggleHistory()} data-testid="live-history" data-count={n}
            title="History: past sessions, goal runs and missions, newest first; a session or mission opens as a replay, a run on its report">
      History · {n}
    </Button>
  );
}

function Row({ r }: { r: HistoryRow }) {
  const models = r.models?.length ? `on ${r.models.map((m) => m.replace(/^[a-z]+:/, "").split("/").pop()).join(", ")}` : "";
  const facts = [KIND[r.kind], ago(r.when), r.secs ? took(r.secs) : "", r.cost != null ? cost(r.cost) : "", r.how, models,
                 r.inside ? `${r.inside} session${r.inside === 1 ? "" : "s"} inside` : ""].filter(Boolean).join(" · ");
  const go = () => (r.kind === "run" ? void openReport(r.id) : void openLiveReplay(r.kind, r.id, r.what).then((ok) => ok && toggleHistory(false)));
  return (
    <button className="lh-row" data-density="row" onClick={go} data-testid="live-history-row" data-kind={r.kind} data-id={r.id} title={`${r.what}\n${facts}\n${r.kind === "run" ? "A click opens its report (Replay is on it)" : "A click opens it as a replay"}`}>
      <span className="lh-what">{short(r.what, 120)}</span>
      <span className="lh-facts mono">{facts}</span>
    </button>
  );
}

export function HistoryDrawer() {
  const open = useHistory((s) => s.open);
  const rows = useHistory((s) => s.rows);
  const loaded = useHistory((s) => s.loaded);
  const replay = useLiveReplay();
  const page = useHistory((s) => s.page);
  const report = useHistory((s) => s.report);
  const reportError = useHistory((s) => s.reportError);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && (e.stopPropagation(), toggleHistory(false));
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open]);
  if (!open) return null;
  return (
    <aside className="lh-drawer" data-testid="live-history-drawer" aria-label="History: past work, newest first">
      <div className="lh-head" data-density="bar" data-testid="live-history-head">
        <b className="lh-title">History</b>
        <span className="mono muted">newest first · a run opens on its report, the rest as a replay</span>
        <span className="spacer" />
        <button className="icon-btn" onClick={() => toggleHistory(false)} aria-label="Close History" title="Close History (Esc)" data-testid="live-history-close">×</button>
      </div>
      {page ? (
        <div className="lh-rows lh-page" data-testid="history-page" data-kind={page.kind} data-id={page.id}>
          {report ? <RunReport data={report} /> : reportError ? <p className="field-error" data-testid="history-report-error">Run {page.id}: {reportError}</p>
            : <div className="mono muted lh-note">reading run {page.id}...</div>}
        </div>
      ) : (
      <div className="lh-rows">
        {!loaded ? <div className="mono muted lh-note">reading the past...</div>
          : !rows.length ? <div className="muted lh-note" data-testid="live-history-none">Nothing past here yet: a session that ends, a run or a mission lands here.</div>
          : rows.map((r) => <Row key={r.kind + r.id} r={r} />)}
      </div>
      )}
      {replay && <div className="mono muted lh-note">Showing a replay: Back to now on the banner returns to what runs.</div>}
    </aside>
  );
}

export const closeHistory = () => history.get().open && toggleHistory(false);
