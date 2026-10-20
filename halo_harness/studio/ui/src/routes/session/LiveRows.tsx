// The Live column's lines (3.1.5.0 R3): each one tagged with its agent (the
// name, a stable colour per agent, the state glyph lit with the agent's
// state; a click on the tag pins that agent), then by kind: its text as it
// types, a tool call as one compact row (the tool, its target, the time
// ticking while it runs, the first line of its result when it lands), an
// output or hand-back as a block, an ask as an amber card with its
// A / R / S / O keys (the attention row's own answers once Studio has read
// it), a spawn, a state change, a steer sent from here.
import { memo, useRef } from "react";
import { Kbd } from "../../lib/ui";
import { short } from "../orchestra/format";
import { answerRow } from "../fleet/extras";
import { panels, usePanels, type AttnRow } from "../fleet/pstore";
import { parseKey, useNow } from "../fleet/store";
import { patchPanel } from "../../lib/workspace/persist";
import type { LiveLine } from "../shared/liveFeed";

export type Who = { name: string; hc: number; state: string };

const ORDER = ["a", "r", "s", "o"];
const DEFAULT_KEYS: Record<string, Record<string, string>> = {
  permission: { a: "allow", r: "deny", s: "stop", o: "open" },
  question: { a: "answer", r: "reply", s: "stop", o: "open" },
  plan: { a: "accept", r: "redo", s: "stop", o: "open" },
  approval: { a: "approve", r: "reject", s: "stop", o: "open" },
};
const GLYPH: Record<string, string> = { running: "●", queued: "○", waiting: "◆", paused: "❚❚", done: "✓", failed: "✕", stopped: "■" };

/** 4s, 1m 05s. */
export function dur(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

function Tag({ k, who, onPin }: { k: string; who: Who; onPin: (k: string) => void }) {
  return (
    <button type="button" className="slv-tag mono" data-testid="session-live-tag" data-hc={who.hc} data-state={who.state} data-key={k}
            onClick={() => onPin(k)} title={`${who.name}: ${who.state || "?"}. Click: show only it (again, or Esc: everyone)`}>
      <span className="slv-glyph" aria-hidden="true">{GLYPH[who.state] || "·"}</span>
      <span className="slv-name">{short(who.name, 18)}</span>
    </button>
  );
}

function ToolRow({ l }: { l: LiveLine }) {
  const now = useNow(!l.ended, 1000);
  const took = l.ended && l.t0 && l.ended > l.t0 + 400 ? dur(l.ended - l.t0) : "";
  return (
    <div className="slv-tool" data-running={!l.ended || undefined} data-error={l.error || undefined}>
      <span className="slv-tool-name mono">{l.tool}</span>
      {l.target && <span className="slv-target mono" title={l.target}>{short(l.target, 90)}</span>}
      <span className="slv-elapsed mono" data-testid="session-live-elapsed">{l.ended ? took : dur(now - l.t0)}</span>
      {l.result !== undefined && <div className="slv-result mono" data-testid="session-live-result">{l.error ? "✕ " : "→ "}{l.result}</div>}
    </div>
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

function Body({ l, live }: { l: LiveLine; live: boolean }) {
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
    case "asked":
      return <div className="slv-note"><span className="mono muted">asked: </span>{short(l.text, 260)}</div>;
    case "you":
      return <div className="slv-you"><span className="mono">you: </span>{short(l.text, 260)}</div>;
    case "state":
    case "error":
      return <div className="slv-state mono" data-state={l.state || (l.kind === "error" ? "failed" : "")}>{short(l.text, 260)}</div>;
    default:
      return <div className="slv-text" data-kind={l.kind} data-typing={live || undefined}>{l.text}</div>;
  }
}

export const LiveRow = memo(function LiveRow({ l, who, last, onPin, onHover }: { l: LiveLine; who: Who; last: boolean; onPin: (k: string) => void; onHover: (k: string) => void }) {
  return (
    <div className="slv-line" data-testid="session-live-line" data-hc={who.hc} data-kind={l.kind} data-key={l.key} data-n={l.n} onMouseEnter={() => onHover(l.key)}>
      <Tag k={l.key} who={who} onPin={onPin} />
      <Body l={l} live={last && who.state === "running" && (l.kind === "text" || l.kind === "thinking")} />
    </div>
  );
});
