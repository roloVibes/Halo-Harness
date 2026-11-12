// Live's History button and drawer (3.3.18.0 "The living canvas"; historyStore.ts holds the rows). The button sits on Live's
// bar with the count; the drawer is closed on load, opens on its click, closes on its x, Esc or the button again. A row
// opens that past thing as a replay on the canvas (replay.ts), the drawer closing behind it. 3.4.0.0 D: a goal run's row
// opens its report as a page of the drawer instead (run/RunReport.tsx), Replay and Back on it. 3.4.1.0 R1 "Time": a
// saved replay file is a row (it opens on the scrubber), and **Open a file** takes a `.halo-replay` from this machine's
// disk -- one made anywhere -- keeps it under <state>/replays/ (POST replays/import) and opens it. 3.4.1.0 R2: each row
// has a tick; two ticked (a session, a goal run, a file) -> Compare, a page of the drawer (Compare.tsx); one ticked ->
// Compare before / after (it with itself); a ticked mission says it is compared from its report. Nothing opens by itself.
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { cost, short } from "../../orchestra/format";
import { history, loadHistory, openCompare, openReport, toggleHistory, useHistory, type HistoryRow } from "./historyStore";
import { tickKey, tickedRefs, toggleTick, useCompare } from "./compareStore";
import { ComparePage } from "./Compare";
import { RunReport } from "../run/RunReport";
import { openFileReplay, openLiveReplay, useLiveReplay } from "./replay";
import { api, ApiError } from "../../../lib/api";
import { toast } from "../../../lib/store";
import { took } from "./GroupBox";

const KIND: Record<string, string> = { session: "session", run: "goal run", mission: "mission", file: "file" };

/** A `.halo-replay` chosen on this machine: checked and kept by the server, then opened on the scrubber. */
async function openChosen(file: File | undefined): Promise<void> {
  if (!file) return;
  try {
    const got = await api.post<{ id: string; path: string }>("replays/import", { text: await file.text() });
    if (await openFileReplay(got.id)) (toast(`Opened ${file.name}; kept at ${got.path}`, "info", 5000), toggleHistory(false));
  } catch (e) {
    toast(`Not a replay this Halo can open: ${e instanceof ApiError ? e.message : String(e)}`, "error", 6000);
  }
}

function OpenFile() {
  return (
    <label className="btn btn-ghost btn-sm lh-open" title="Open a .halo-replay file saved here or on another machine (halo replay save, or Save this run's replay); it is kept under the state dir's replays/" data-testid="live-history-open">
      Open a file
      <input type="file" accept=".halo-replay,application/json" className="sr-only" onChange={(e) => void openChosen(e.target.files?.[0]).then(() => (e.target.value = ""))} data-testid="live-history-file" />
    </label>
  );
}

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
  const facts = [KIND[r.kind], ago(r.when), r.secs ? took(r.secs) : "", r.cost != null ? cost(r.cost) : "", r.how, models].filter(Boolean).join(" · ");
  const go = () => (r.kind === "run" ? void openReport(r.id) : r.kind === "file" ? void openFileReplay(r.id).then((ok) => ok && toggleHistory(false))
    : void openLiveReplay(r.kind, r.id, r.what).then((ok) => ok && toggleHistory(false)));
  const key = tickKey(r);
  const on = useCompare((s) => s.ticked.includes(key));
  return (
    <div className="lh-item" data-ticked={on || undefined}>
      <label className="lh-tick" title={r.kind === "mission" ? "A mission is compared from its report (the fleet pack's mission page)" : "Tick two to compare them; one ticked compares it before / after a moment"}>
        <input type="checkbox" checked={on} onChange={() => toggleTick(key)} data-testid="live-history-tick" data-kind={r.kind} data-id={r.id} aria-label={`Tick ${short(r.what, 60)} to compare`} />
      </label>
      <button className="lh-row" data-density="row" onClick={go} data-testid="live-history-row" data-kind={r.kind} data-id={r.id} title={`${r.what}\n${facts}\n${r.kind === "run" ? "A click opens its report (Replay is on it)" : "A click opens it as a replay"}`}>
        <span className="lh-what">{short(r.what, 120)}</span>
        <span className="lh-facts mono">{facts}</span>
      </button>
    </div>
  );
}

/** The Compare button (shown once a row is ticked) and, when a mission is ticked, why it is left out. */
function CompareBar() {
  const ticked = useCompare((s) => s.ticked);
  if (!ticked.length) return null;
  const { refs, mission } = tickedRefs(ticked);
  const go = () => (refs.length === 2 ? openCompare(refs[0], refs[1]) : refs.length === 1 && openCompare(refs[0], refs[0]));
  return (
    <div className="lh-compare" data-density="bar" data-testid="live-history-comparebar">
      <Button size="sm" variant="primary" disabled={!refs.length} onClick={go} data-testid="live-history-compare" data-n={refs.length}
              title={refs.length === 2 ? "Compare the two ticked runs side by side (no model call, nothing written)" : "Compare this run with itself: before / after a moment (its first steer, else halfway)"}>
        {refs.length === 1 ? "Compare before / after" : "Compare"}
      </Button>
      <span className="mono muted">{refs.length} ticked{refs.length < 2 ? " · tick another to compare two" : ""}</span>
      {mission && <span className="muted lh-mission" data-testid="compare-mission-note">A mission is compared from its report (the fleet pack's mission page), not here.</span>}
    </div>
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
    <aside className="lh-drawer" data-testid="live-history-drawer" aria-label="History: past work, newest first" data-wide={page?.kind === "compare" || undefined}>
      <div className="lh-head" data-density="bar" data-testid="live-history-head">
        <b className="lh-title">History</b>
        <span className="mono muted" title="Newest first. A goal run opens on its report, the rest as a replay; tick two rows to compare them">newest first · a run opens on its report, the rest as a replay · tick two to compare</span>
        <span className="spacer" />
        <OpenFile />
        <button className="icon-btn" onClick={() => toggleHistory(false)} aria-label="Close History" title="Close History (Esc)" data-testid="live-history-close">×</button>
      </div>
      {page ? (
        <div className="lh-rows lh-page" data-testid="history-page" data-kind={page.kind} data-id={page.id}>
          {page.kind === "compare" ? <ComparePage /> : report ? <RunReport data={report} /> : reportError ? <p className="field-error" data-testid="history-report-error">Run {page.id}: {reportError}</p>
            : <div className="mono muted lh-note">reading run {page.id}...</div>}
        </div>
      ) : (
      <>
      <CompareBar />
      <div className="lh-rows">
        {!loaded ? <div className="mono muted lh-note">reading the past...</div>
          : !rows.length ? <div className="muted lh-note" data-testid="live-history-none">Nothing past here yet: a session that ends, a run or a mission lands here.</div>
          : rows.map((r) => <Row key={r.kind + r.id} r={r} />)}
      </div>
      </>
      )}
      {replay && <div className="mono muted lh-note">Showing a replay: Back to now on the banner returns to what runs.</div>}
    </aside>
  );
}

export const closeHistory = () => history.get().open && toggleHistory(false);
