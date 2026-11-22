// `Change session` (3.6.0.2 P28; split from PromptHead.tsx in 3.6.0.11 so the Feed's head and Cost open the same list):
// the button, and, open, every open session in the header's words (<folder> · <title> · started HH:MM · in a terminal),
// newest first, the current one marked; choosing one sets the pick (a pick by hand: store.ts never moves it by itself).
// The list hangs under the nearest positioned box (.spp-head, .slv-head, .sco-change). `chip` (the Feed's head: "{n}
// other sessions running") is a second door to the same list. `useWatched`: the pick, the open rows and, when the
// watched session ended while another runs, the line Cost and Prompt say in place of "No session here yet".
import { useEffect, useRef, useState } from "react";
import { Button } from "../../lib/ui";
import { useFleet } from "../fleet/store";
import type { SessionRow } from "../fleet/types";
import { choseInList, lastRow, openOrder } from "./pick";
import { CHANGE_SESSION, endedLine, headParts, NO_TERMINAL, othersLine } from "./promptWords";
import { chosenSession, localSessions, openSession, useSession } from "./store";

const NONE: SessionRow[] = []; // one empty list: a selector that made a new one each read would never settle

export function Words({ row, now }: { row: SessionRow; now: number }) {
  const p = headParts(row, now);
  return (
    <>
      <span className="spp-folder">{p.folder}</span>
      <span className="spp-dot-sep"> · </span><span className="spp-title muted">{p.title}</span>
      {p.started && <><span className="spp-dot-sep"> · </span><span className="muted">{p.started}</span></>}
      <span className="spp-dot-sep"> · </span>
      {p.terminal === NO_TERMINAL ? <span className="og-chip mono">{p.terminal}</span> : <span className="spp-term">{p.terminal}</span>}
    </>
  );
}

function SessionList({ rows, pick, keep, onDone }: { rows: SessionRow[]; pick: string; keep: { current: HTMLElement | null }; onDone: () => void }) {
  const ref = useRef<HTMLUListElement>(null);
  useEffect(() => {
    const away = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && !keep.current?.contains(e.target as Node) && onDone();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onDone();
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => (document.removeEventListener("mousedown", away), document.removeEventListener("keydown", esc));
  }, [onDone, keep]);
  const now = Date.now();
  const newest = [...rows].sort((a, b) => (Number(b.started) || 0) - (Number(a.started) || 0) || (a.session_id < b.session_id ? -1 : 1));
  const choose = (sid: string) => {
    choseInList(sid, pick);
    onDone();
    openSession({ session: sid });
  };
  return (
    <ul className="spp-pick" ref={ref} role="listbox" aria-label={CHANGE_SESSION} data-testid="prompt-pick-list">
      {newest.map((r) => (
        <li key={r.session_id} role="option" aria-selected={r.session_id === pick} className="spp-pick-item" data-testid="prompt-pick-item"
            data-session={r.session_id} data-on={r.session_id === pick || undefined} onClick={() => choose(r.session_id)}>
          <span className="spp-pick-mark" aria-hidden="true">{r.session_id === pick ? "●" : ""}</span>
          <span className="spp-pick-words"><Words row={r} now={now} /></span>
        </li>
      ))}
    </ul>
  );
}

export function ChangeSession({ rows, pick, testid, chip }: { rows: SessionRow[]; pick: string; testid: string; chip?: string }) {
  const [open, setOpen] = useState(false);
  const doors = useRef<HTMLSpanElement>(null);
  return (
    <>
      <span className="chg-doors" ref={doors}>
        {chip !== undefined && ( // its room is kept while no other session runs (hidden), so the button never moves
          <button type="button" className="slv-others mono" onClick={() => setOpen(!open)} aria-expanded={open} data-testid="session-feed-others"
                  data-on={!!chip || undefined} aria-hidden={!chip || undefined} tabIndex={chip ? undefined : -1}
                  title={`${CHANGE_SESSION}: every open session`}>{chip || othersLine(1)}</button>
        )}
        <Button size="sm" variant="ghost" onClick={() => setOpen(!open)} disabled={!rows.length} aria-expanded={open} data-testid={testid}>
          {CHANGE_SESSION}
        </Button>
      </span>
      {open && <SessionList rows={rows} pick={pick} keep={doors} onDone={() => setOpen(false)} />}
    </>
  );
}

/** The pick (open or ended), its row (an ended one's last row), the open rows, and the ended line ("" unless the watched
 *  session ended while another is open). */
export function useWatched(): { pick: string; row: SessionRow | null; rows: SessionRow[]; ended: string } {
  const ss = useFleet(chosenSession);
  const rows = useFleet((s) => (localSessions(s).length ? localSessions(s) : NONE));
  const chosen = useSession((x) => x.chosen);
  const pick = useFleet((s) => s.scope.session || "") || chosen;
  const gone = !ss && pick ? lastRow(pick)?.row || null : null;
  return { pick: ss ? ss.session_id : pick, row: ss || gone, rows, ended: gone ? endedLine(openOrder(rows)[0]) : "" };
}
