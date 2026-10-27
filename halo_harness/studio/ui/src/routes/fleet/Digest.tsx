// "While you were away": when the tab comes back after more than AWAY_MS
// (or Studio opens after that long), the digest since you last looked
// (`GET fleet/digest?since=`, computed in code: sessions started and ended,
// cost, decisions and who made them, files touched, errors, hand-offs, per
// harness) shows as a card on the Fleet Start view and at the top of the Fleet
// Tree panel (3.3.2.0 R2: the expanded rail before; the Fleet icon in the rail
// carries a dot while it waits, and a click on it opens the Tree). When you
// last looked is localStorage `halo.fleet.lastSeen` (ms): refreshed every
// minute while the tab shows and when it hides; Dismiss sets it to now.
import { useEffect } from "react";
import { Button, Icon } from "../../lib/ui";
import { cost } from "../orchestra/format";
import { loadDigest } from "./pload";
import { panels, usePanels, type Digest } from "./pstore";

export const SEEN_KEY = "halo.fleet.lastSeen";
const AWAY_MS = 10 * 60 * 1000;
const BEAT_MS = 60 * 1000;
let started = false;

function readSeen(): number {
  try {
    return Number(localStorage.getItem(SEEN_KEY)) || 0;
  } catch {
    return 0;
  }
}

function writeSeen(ms = Date.now()): void {
  try {
    localStorage.setItem(SEEN_KEY, String(ms));
  } catch {
    /* storage off: no digest in this browser */
  }
}

/** Away for more than AWAY_MS (or `force`): read what happened since. */
export async function checkAway(force = false): Promise<void> {
  const seen = readSeen();
  const now = Date.now();
  if (!seen && !force) return writeSeen(now);
  if (force || now - seen > AWAY_MS) await loadDigest(seen || now - 86_400_000);
}

export function dismissDigest(): void {
  writeSeen();
  panels.update(() => ({ digestOpen: false }));
}

/** Start once (the rail's section icons do, in every section). */
export function startDigest(): void {
  if (started) return;
  started = true;
  void checkAway();
  const beat = () => !document.hidden && !panels.get().digestOpen && writeSeen();
  window.setInterval(beat, BEAT_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) beat();
    else void checkAway();
  });
  window.addEventListener("focus", () => void checkAway());
  window.addEventListener("pagehide", () => !panels.get().digestOpen && writeSeen());
}

function span(d: Digest): string {
  const m = Math.max(1, Math.round((d.until - d.since) / 60));
  return m < 120 ? `${m} min` : m < 2880 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} days`;
}

/** True while a digest waits to be read (the Fleet icon's dot). */
export const useAway = (): boolean => usePanels((s) => s.digestOpen && !!s.digest);

export function DigestCard({ where }: { where: "tree" | "start" }) {
  useEffect(() => startDigest(), []);
  const open = usePanels((s) => s.digestOpen);
  const d = usePanels((s) => s.digest);
  if (!open || !d) return null;
  const t = d.totals;
  const busy = d.harnesses.filter((h) => !h.quiet);
  return (
    <section className="fdg glass" data-where={where} data-testid="fleet-digest" aria-label="While you were away">
      <div className="fdg-head">
        <span className="rail-label mono">WHILE YOU WERE AWAY · {span(d)}</span>
        <button className="icon-btn" onClick={dismissDigest} aria-label="Dismiss" title="Dismiss: next time it counts from now" data-testid="fleet-digest-dismiss">
          <Icon name="close" />
        </button>
      </div>
      {!busy.length ? (
        <p className="muted fdg-quiet">Nothing happened: no session started or ended, nothing was decided.</p>
      ) : (
        <>
          <div className="fdg-totals mono" data-testid="fleet-digest-totals">
            <span><b>{t.started}</b> started</span>
            <span><b>{t.ended}</b> ended</span>
            <span><b>{cost(t.cost_usd)}</b></span>
            <span><b>{t.decisions}</b> decided</span>
            <span><b>{t.files}</b> files</span>
            {t.errors > 0 && <span className="fdg-bad"><b>{t.errors}</b> errors</span>}
            {t.handoffs > 0 && <span><b>{t.handoffs}</b> hand-offs</span>}
          </div>
          <ul className="fdg-list">
            {busy.map((h) => (
              <li key={h.id} data-testid="fleet-digest-harness">
                <b>{h.name}</b>
                <span className="muted">
                  {[h.started.length && `${h.started.length} started`, h.ended.length && `${h.ended.length} ended`, h.cost_usd > 0 && cost(h.cost_usd),
                    h.decisions.length && `${h.decisions.length} decided (${[...new Set(h.decisions.map((x) => x.by))].join(", ")})`,
                    h.files.length && `${h.files.length} file${h.files.length === 1 ? "" : "s"}`, h.errors.length && `${h.errors.length} error${h.errors.length === 1 ? "" : "s"}`,
                    h.handoffs.length && `${h.handoffs.length} hand-off${h.handoffs.length === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {where === "start" && <Button size="sm" variant="ghost" onClick={dismissDigest}>Got it</Button>}
    </section>
  );
}
