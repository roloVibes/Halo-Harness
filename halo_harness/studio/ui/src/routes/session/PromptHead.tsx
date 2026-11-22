// The Prompt panel's header (3.6.0.2 P27-P29, P31, "one prompt": the owner's point 21). It names the session the box
// types into in words, never an id: `<folder> · <title> · started <HH:MM> · in a terminal | no terminal`
// (promptWords.ts headParts), on their own row under PROMPT, the state and `Change session`. The words always take the height of two lines: a long title wraps into the second and
// is never cut, so the box under it never moves. `Change session` lists every open session in the same words, newest
// first, the current one marked; choosing one sets the pick (ChangeSession.tsx). When the pick changes any other way (an agent selected on
// the Map, `/studio` from another terminal, P31's follow) a line stands in the words' place for 6 s, in amber:
// `Now typing into <folder> · <title>.` (the short `Now typing into <folder>.` when the title would not fit the two
// lines), or `Same terminal, new conversation: <folder>.` after /clear, a fork or /resume in that terminal.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChangeSession, Words } from "./ChangeSession";
import { NoTerminal } from "./NewSession";
import { followedFrom, tookFromList } from "./pick";
import type { SessionRow } from "../fleet/types";
import { followLine, LINE_MS, movedLine } from "./promptWords";

const TWO_LINES = 32; // px: the words' two lines (styles/prompt.css .spp-words)

/** `row`: the session the box types into (the ended pick's last row while P32 holds); `pick` its id; `rows` the open ones. */
export function PromptHead({ row, pick, rows, state }: { row: SessionRow | null; pick: string; rows: SessionRow[]; state: string }) {
  const [line, setLine] = useState<{ row: SessionRow; follow: boolean } | null>(null);
  const [short, setShort] = useState(false);
  const [fit, setFit] = useState(0); // the words' height when the line came: the line keeps it, so nothing moves
  const words = useRef<HTMLSpanElement>(null);
  const was = useRef(pick);
  useEffect(() => {
    const before = was.current;
    was.current = pick;
    const chose = tookFromList(pick);
    if (!before || !pick || before === pick || chose || !row || row.session_id !== pick) return void setLine(null);
    setShort(false);
    setFit(words.current?.clientHeight || 0);
    setLine({ row, follow: followedFrom(pick) === before });
    const t = window.setTimeout(() => setLine(null), LINE_MS);
    return () => window.clearTimeout(t);
  }, [pick]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { // P29: the long line would pass two lines: the short one, before it is painted
    const said = words.current?.querySelector<HTMLElement>(".spp-moved");
    if (line && !line.follow && !short && said && said.offsetHeight > TWO_LINES + 1) setShort(true);
  }, [line, short]);
  const said = line ? (line.follow ? followLine(line.row) : movedLine(line.row, short)) : "";
  return (
    <header className="spp-head">
      <div className="spp-head-bar">
        <span className="rail-label mono">PROMPT</span>
        {row?.kind === "headless" && row.session_id === pick && <NoTerminal ss={row} chip={false} />}
        <span className="mono muted spp-head-state" data-testid="prompt-state">{row ? state : ""}</span>
        <ChangeSession rows={rows} pick={pick} testid="prompt-change" />
      </div>
      <span className="spp-words" ref={words} data-testid="prompt-to" data-line={line ? (line.follow ? "follow" : "moved") : undefined}
            style={line && fit ? { minHeight: fit } : undefined} title={row?.cwd || undefined}>
        {said ? <span className="spp-moved" data-testid="prompt-moved">{said}</span> : <span className="spp-words-in">{row ? <Words row={row} now={Date.now()} /> : "no session"}</span>}
      </span>
    </header>
  );
}
