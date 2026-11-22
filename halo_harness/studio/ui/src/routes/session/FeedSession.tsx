// The Feed's session line (3.6.0.11, reader E (d); the owner: "The session gui view doesn't synch with the terminal"):
// the last row of the Feed's head names the session the Feed, its Steer box and the Prompt box speak of, in the Prompt
// header's words (<folder> · <title> · started HH:MM · in a terminal), with `Change session`; while other sessions are
// open a chip "{n} other session(s) running" opens the same list. When Session moved by itself to a newer session
// (store.ts, pick.ts autoPick) the line says so for LINE_MS: "Now typing into <folder> · <title>.". The row is drawn from
// the first draw ("no session" with none), so nothing under it moves when a session arrives; a long line wraps, never cut.
import { useEffect, useState } from "react";
import { ChangeSession, useWatched, Words } from "./ChangeSession";
import { autoMovedTo } from "./pick";
import { LINE_MS, movedLine, othersLine } from "./promptWords";

export function FeedSession() {
  const { pick, row, rows } = useWatched();
  const [moved, setMoved] = useState("");
  useEffect(() => {
    if (!autoMovedTo(pick)) return void setMoved("");
    setMoved(pick);
    const t = window.setTimeout(() => setMoved(""), LINE_MS);
    return () => window.clearTimeout(t);
  }, [pick]);
  const others = rows.filter((r) => r.session_id !== row?.session_id).length;
  const said = row && moved === row.session_id ? movedLine(row, false) : "";
  return (
    <div className="slv-session" data-testid="session-feed-session" data-sid={row?.session_id || undefined} title={row?.cwd || undefined}>
      <span className="slv-session-words" data-testid="session-feed-words" data-line={said ? "moved" : undefined}>
        {said ? <span className="spp-moved">{said}</span> : row ? <Words row={row} now={Date.now()} /> : <span className="muted">no session</span>}
      </span>
      <ChangeSession rows={rows} pick={pick} testid="session-feed-change" chip={othersLine(others)} />
    </div>
  );
}
