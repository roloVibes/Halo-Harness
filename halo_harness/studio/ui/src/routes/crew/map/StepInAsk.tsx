// What an agent of the step-in card asks you (P4 batch 9: an ask's door opens the card on the asking agent's box, and the
// card carries the ask's choices): each attention row of the card's agents, its question in its own words, and its
// answers as the row's own keys and words (A / R / S, as Attention offers them; O is where you are already). An answer
// that needs words (R on a question or a plan) opens a field first. Every answer goes through fleet/extras.ts answerRow,
// the path Attention's keys take.
import { useState } from "react";
import { Button } from "../../../lib/ui";
import { answerRow } from "../../fleet/extras";
import { usePanels, type AttnRow } from "../../fleet/pstore";
import type { Who } from "./stepInTarget";

const KEYS = ["a", "r", "s"];
const keyOf = (r: AttnRow) => `${r.harness}|${r.session_id || ""}|${r.agent_id || "main"}`;

function Ask({ row }: { row: AttnRow }) {
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState("");
  const needs = row.kind !== "permission";
  const send = () => (needs && !text.trim() ? undefined : void answerRow(row, "r", text.trim()));
  return (
    <div className="mp-step-in-ask" data-testid="map-step-in-ask" data-id={row.id} data-kind={row.kind}>
      <span className="mp-step-in-ask-what mono">{row.what}</span>
      <span className="mp-step-in-acts">
        {KEYS.filter((k) => row.keys[k]).map((k) => (
          <Button key={k} size="sm" data-testid="map-step-in-ask-key" data-key={k}
                  onClick={() => (k === "r" && row.text_for === "r" ? setTyping(true) : void answerRow(row, k))}>{row.keys[k]}</Button>
        ))}
      </span>
      {typing && (
        <span className="mp-step-in-ask-reply">
          <input className="input" autoFocus value={text} onChange={(e) => setText(e.target.value)} aria-label={row.keys.r}
                 data-testid="map-step-in-ask-text" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), send())} />
          <Button size="sm" variant="primary" disabled={needs && !text.trim()} onClick={send}>{row.keys.r}</Button>
        </span>
      )}
    </div>
  );
}

/** The asks of the card's agents, in the sheet's body (3.6.0.14 O1-4: the body alone scrolls, so an ask arriving or
 *  answered moves nothing outside it). `part` "open": the asks present when the sheet opened (`seen`, their ids, taken at
 *  its first draw), at the body's top; "later": the asks that came after, at the body's END. A paused agent's row is not
 *  one: its answer, Resume, is the sheet's own Resume. O1-6: `from` / `to` cut the later rows around a late Last said. */
export function StepInAsks({ who, part, seen, from = 0, to }: { who: Who[]; part: "open" | "later"; seen: Set<string>; from?: number; to?: number }) {
  const rows = askRows(usePanels((s) => s.attention), who, part, seen).slice(from, to);
  return <div className="mp-step-in-asks" data-testid="map-step-in-asks" data-part={part}>{rows.map((r) => <Ask key={r.id} row={r} />)}</div>;
}

/** The asks of `part` among the attention rows `attn`. */
export function askRows(attn: AttnRow[], who: Who[], part: "open" | "later", seen: Set<string>): AttnRow[] {
  const keys = new Set(who.map((w) => w.key));
  return attn.filter((r) => r.kind !== "paused" && keys.has(keyOf(r)) && seen.has(r.id) === (part === "open"));
}
