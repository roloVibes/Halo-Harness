// A THINK row's body and the thought under an action row (3.3.16.2, the owner: "it's really amazing to get more
// visualization on what the models are really thinking"). The thought reads as inner voice: muted sans italic on a
// hairline rule in the --think token, a caret while it grows, clamped to four lines with "show all" / "show less" on
// the row (the row grows; nothing overlaps), and once it ended a small mono suffix: how long it thought and, when the
// provider reported them, its tokens. Its chip says what it led to and scrolls to that row. Under an action row, the
// `why?` chip opens the thought that preceded it here (`live-why`), with "what the model saw" (Why.tsx) beside it.
// The agent inspector's Thinking tab draws its thoughts with the same `Clamp` (StreamViews.tsx).
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { LiveLine } from "../shared/liveFeed";
import { ledWords, thoughtTook } from "../shared/liveThink";
import { askWhy } from "./Why";

/** Text clamped to `lines` lines with show all / show less when it overflows; `caret` while it grows. */
export function Clamp({ text, caret = false, lines = 4, className = "", testid }: { text: string; caret?: boolean; lines?: number; className?: string; testid?: string }) {
  const [all, setAll] = useState(false);
  const [over, setOver] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (el && !all) setOver(el.scrollHeight > el.clientHeight + 1);
  }, [text, all]);
  return (
    <div className={"slv-clamp " + className} data-open={all || undefined}>
      <div ref={box} className="slv-clamp-text" style={all ? undefined : { WebkitLineClamp: lines }} data-testid={testid} data-typing={caret || undefined}>
        {text}
      </div>
      {(over || all) && (
        <button type="button" className="og-link mono slv-more" data-testid="live-show-all" aria-expanded={all} onClick={() => setAll(!all)}>
          {all ? "show less" : "show all"}
        </button>
      )}
    </div>
  );
}

/** Scroll the Live column to row `n` (a thought's act, a timeline segment's thought) and light it once. */
export function goRow(n: number): void {
  const box = document.querySelector<HTMLElement>(`[data-testid="session-live-scroll"]`);
  const el = box?.querySelector<HTMLElement>(`[data-n="${n}"]`);
  if (!box || !el) return;
  // its first line at the top (a tall row starts in view), again once the column has settled (a pause redraws it)
  const align = () => el.isConnected && (box.scrollTop += el.getBoundingClientRect().top - box.getBoundingClientRect().top - 8);
  align();
  for (const ms of [120, 400]) window.setTimeout(align, ms);
  el.dataset.flash = "1";
  window.setTimeout(() => delete el.dataset.flash, 1200);
}

export function ThinkBody({ l, live, led, ledN = 0 }: { l: LiveLine; live: boolean; led?: LiveLine; ledN?: number }) {
  const took = thoughtTook(l);
  const words = ledWords(led, ledN);
  return (
    <div className="slv-think" data-done={l.done || undefined}>
      <Clamp text={l.text} caret={l.tid ? !l.done : live} className="slv-think-text" testid="live-think-text" />
      {(took || words) && (
        <div className="slv-think-foot mono">
          {took && <span className="slv-think-took" data-testid="live-think-took">{took}</span>}
          {words && (
            <button type="button" className="slv-led" data-testid="live-think-led" onClick={() => goRow(led!.n)} title="Show the row this thought led to">
              {words} ↓
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Under an action row: the thought that preceded it (its first answer to "why?"), and the turn's postmortem a click on. */
export function WhyThought({ l, thought, extra }: { l: LiveLine; thought: LiveLine; extra?: ReactNode }) {
  return (
    <div className="slv-why-thought" data-testid="live-why">
      <div className="slv-why-head mono">
        <span>THE THOUGHT BEFORE IT</span>
        <button type="button" className="og-link mono" onClick={() => goRow(thought.n)} title="Show the THINK row">at its row ↑</button>
        <button type="button" className="og-link mono" onClick={() => void askWhy(l)} title="Why this answer? What the model saw for this turn (the Inspector shows it)">what the model saw</button>
        {extra}
      </div>
      <Clamp text={thought.text} className="slv-think-text" />
    </div>
  );
}
