// The Live column's lines (3.1.5.0 R3): each one tagged with its agent (the
// name, a stable colour per agent, the state glyph lit with the agent's
// state; a click on the tag pins that agent), then by kind: its text as it
// types, a tool call as one compact row (LiveTool.tsx: the tool, its target,
// the time ticking while it runs, the first line of its result when it lands,
// the whole result a click away), an output or hand-back as a block, an ask
// as an amber card with its A / R / S / O keys (the attention row's own
// answers once Studio has read it), a spawn, a state change, a steer sent
// from here. 3.1.7.0 R1 (the owner: "I want what fleet has ... within the
// session tab"): Fleet's log columns lead every line, the time (HH:MM:SS)
// and the KIND in the Activity log's own mono classes (fleet-panels2.css
// `.fac-line`, its container query: under 440 px the time, the kind and the
// tag share a row and the line's body runs full width under them), and the
// tag carries a "steer" button on hover (steer.ts: pin it, the box focused).
// 3.3.0.0 R6: the steer's target row carries `data-target` (a steady outline);
// a click on a row (or `s` with the focus on it) makes it the target (a click
// on its own controls -- the tag, an ask's keys, a tool row that opens -- does
// what that control does); a steer
// reads "↳ steer to <agent>: ..." under it and the agent's next row is marked
// "after your steer".
import { memo, useRef, type MouseEvent } from "react";
import { Kbd } from "../../lib/ui";
import { clock, short } from "../orchestra/format";
import { answerRow } from "../fleet/extras";
import { panels, usePanels, type AttnRow } from "../fleet/pstore";
import { parseKey } from "../fleet/store";
import { patchPanel } from "../../lib/workspace/persist";
import type { LiveKind, LiveLine } from "../shared/liveFeed";
import { ToolRow } from "./LiveTool";
import { steerAgent } from "./steer";

export type Who = { name: string; hc: number; state: string };

/** The KIND column, Fleet's log vocabulary. */
export const KIND: Record<LiveKind, string> = {
  text: "TEXT", thinking: "THINK", tool: "TOOL", output: "OUT", ask: "ASK", spawn: "SPAWN", state: "STATE", you: "YOU", asked: "ASKED", error: "ERR",
  pack: "PACK", // 3.2.0.0 R3: the pack's own label shows instead when it declares one
};

const ORDER = ["a", "r", "s", "o"];
const DEFAULT_KEYS: Record<string, Record<string, string>> = {
  permission: { a: "allow", r: "deny", s: "stop", o: "open" },
  question: { a: "answer", r: "reply", s: "stop", o: "open" },
  plan: { a: "accept", r: "redo", s: "stop", o: "open" },
  approval: { a: "approve", r: "reject", s: "stop", o: "open" },
};
export const GLYPH: Record<string, string> = { running: "●", queued: "○", waiting: "◆", paused: "❚❚", done: "✓", failed: "✕", stopped: "■" };

function Tag({ k, who, onPin }: { k: string; who: Who; onPin: (k: string) => void }) {
  return (
    <span className="slv-who">
      <button type="button" className="slv-tag mono" data-testid="session-live-tag" data-hc={who.hc} data-state={who.state} data-key={k}
              onClick={() => onPin(k)} title={`${who.name}: ${who.state || "?"}. Click: show only it (again, or Esc: everyone)`}>
        <span className="slv-glyph" aria-hidden="true">{GLYPH[who.state] || "·"}</span>
        <span className="slv-name">{short(who.name, 18)}</span>
      </button>
      <button type="button" className="slv-steer-tag mono" data-testid="session-live-steer-tag" tabIndex={-1} onClick={() => steerAgent(k)}
              title={`Steer ${who.name}: the Steer box at the bottom, addressed to it`}>
        steer ▸
      </button>
    </span>
  );
}

const rowOf = (rows: AttnRow[], key: string): AttnRow | undefined => {
  const { s, a } = parseKey(key);
  return rows.find((r) => r.session_id === s && (!r.agent_id || r.agent_id === a));
};

/** The attention row this ask became (same session, same agent), once Studio has read it. */
function useRowFor(k: string): AttnRow | undefined {
  return usePanels((st) => rowOf(st.attention, k));
}

/** A / R / S / O on an ask: the attention row's own answer (R with a text, and an ask Studio has not read yet, open Attention). */
export function answerAsk(key: string, k: string, byKey = false): boolean {
  const row = rowOf(panels.get().attention, key);
  if (!row) {
    if (!byKey) patchPanel("session", "session-attention", { collapsed: false }, false);
    return false;
  }
  if (!row.keys[k]) return false;
  if (k === "r" && row.text_for === "r") {
    patchPanel("session", "session-attention", { collapsed: false }, false);
    panels.update(() => ({ replyFor: row.id, attnSel: row.id }));
  } else void answerRow(row, k);
  return true;
}

function AskCard({ l }: { l: LiveLine }) {
  const row = useRowFor(l.key);
  const seen = useRef(false);
  if (row) seen.current = true;
  const keys = row?.keys || DEFAULT_KEYS[l.ask || ""] || DEFAULT_KEYS.permission;
  const press = (k: string) => answerAsk(l.key, k);
  return (
    <div className="slv-ask" data-testid="session-live-ask" data-answered={(seen.current && !row) || undefined}>
      <div className="slv-ask-what">{l.text}</div>
      <div className="slv-ask-keys">
        {ORDER.filter((k) => keys[k]).map((k) => (
          <button key={k} type="button" className="fat-key" data-key={k} data-testid="session-live-key" onClick={() => press(k)} disabled={seen.current && !row}
                  title={row ? `${keys[k]} (the Attention row's answer)` : "Studio is reading its answers: this opens Attention"}>
            <Kbd keys={k.toUpperCase()} /> {keys[k]}
          </button>
        ))}
        {seen.current && !row && <span className="mono muted">answered</span>}
      </div>
    </div>
  );
}

function Body({ l, live, name }: { l: LiveLine; live: boolean; name: string }) {
  switch (l.kind) {
    case "tool":
      return <ToolRow l={l} />;
    case "ask":
      return <AskCard l={l} />;
    case "output":
      return (
        <div className="slv-out" data-state={l.state}>
          <div className="slv-out-head mono">{l.state === "done" ? "DONE · ITS LAST WORDS" : "HANDS BACK"}</div>
          <div className="slv-out-text">{short(l.text, 900)}</div>
        </div>
      );
    case "spawn":
      return <div className="slv-note mono" data-kind="spawn">◉ {short(l.text, 200)}</div>;
    case "pack":
      return <div className="slv-note" data-kind="pack" data-testid="session-live-pack">{short(l.text, 260)}</div>;
    case "asked":
      return <div className="slv-note"><span className="mono muted">asked: </span>{short(l.text, 260)}</div>;
    case "you":
      return <div className="slv-you" data-testid="live-steer-row"><span className="mono">↳ steer to {l.to || name}: </span>{short(l.text, 260)}</div>;
    case "state":
    case "error":
      return <div className="slv-state mono" data-state={l.state || (l.kind === "error" ? "failed" : "")}>{short(l.text, 260)}</div>;
    default:
      return <div className="slv-text" data-kind={l.kind} data-typing={live || undefined}>{l.text}</div>;
  }
}

type RowProps = { l: LiveLine; who: Who; last: boolean; target: boolean; onPin: (k: string) => void; onHover: (k: string) => void; onTarget: (l: LiveLine) => void };

export const LiveRow = memo(function LiveRow({ l, who, last, target, onPin, onHover, onTarget }: RowProps) {
  const pick = (e: MouseEvent) => !(e.target as HTMLElement).closest(".slv-who, .slv-ask-keys, button, a, [role=button]") && onTarget(l);
  return (
    <div className="fac-line slv-line" data-testid="session-live-line" data-hc={who.hc} data-kind={l.kind} data-key={l.key} data-n={l.n} data-target={target || undefined}
         data-after={l.after || undefined} tabIndex={target ? 0 : -1} onMouseEnter={() => onHover(l.key)} onClick={pick}
         title={target ? `Your steer goes to ${who.name}, under this row` : undefined}>
      <span className="mono fac-ts" data-testid="session-live-time">{clock(l.ts)}</span>
      <span className="mono fac-kind" data-testid="session-live-kind">{l.label || KIND[l.kind] || l.kind}</span>
      <Tag k={l.key} who={who} onPin={onPin} />
      <div className="fac-text slv-body">
        {l.after && <span className="slv-after mono" data-testid="live-after-steer">after your steer</span>}
        <Body l={l} name={who.name} live={last && who.state === "running" && (l.kind === "text" || l.kind === "thinking")} />
      </div>
    </div>
  );
});
