// The three streams of one agent. Thinking: what it writes and reasons, as
// it arrives (the newest text types out character by character), with the
// steers (yours marked "you"), notes and controls between. Working: one row
// per tool call with its arguments, the file it touches, its result, and for
// Edit / Write the diff as it grows. Output: its hand-back, else the text it
// wrote after its last tool call.
import { useEffect, useRef, useState } from "react";
import { Icon, toolIcon } from "../../lib/ui";
import { outputOf, thinkingOf, workingOf, type ToolRow } from "./streams";
import type { Entry } from "./types";

/** Text that types out as it grows: catches up in about 20 frames, never all at once.
 *  `fresh`: a block that just arrived types from its first character. */
export function Typed({ text, live, fresh = false }: { text: string; live: boolean; fresh?: boolean }) {
  const [n, setN] = useState(fresh && live ? 0 : text.length);
  const cur = useRef(n);
  useEffect(() => {
    if (!live) {
      cur.current = text.length;
      setN(text.length);
      return;
    }
    let raf = 0;
    const step = () => {
      const left = text.length - cur.current;
      if (left <= 0) {
        cur.current = text.length;
        setN(text.length);
        return;
      }
      cur.current += Math.max(1, Math.ceil(left / 20));
      setN(cur.current);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [text, live]);
  const shown = text.slice(0, Math.min(n, text.length));
  return (
    <span className="fa-typed" data-typing={live && n < text.length ? "true" : undefined}>
      {shown}
      {live && <span className="fa-caret" aria-hidden="true" />}
    </span>
  );
}

const when = (ts?: number | null) => (ts ? new Date((ts > 1e12 ? ts : ts * 1000)).toTimeString().slice(0, 8) : "");

function ThinkingRow({ e, last, live }: { e: Entry; last: boolean; live: boolean }) {
  if (e.kind === "user")
    return (
      <div className="fa-row fa-user" data-you={e.you || undefined} data-testid={e.you ? "fleet-steer-echo" : undefined}>
        <span className="fa-who mono">{e.you ? `you · ${e.mode || "nudge"}` : e.tag === "steer" || /^\[steer/.test(e.text || "") ? "steer" : "asked"}</span>
        <span className="fa-text">{e.text}</span>
      </div>
    );
  if (e.kind === "control" || e.kind === "note" || e.kind === "done" || e.kind === "ask" || e.kind === "error")
    return (
      <div className="fa-row fa-note" data-kind={e.kind}>
        <span className="fa-who mono">{e.kind === "ask" ? "needs you" : e.kind}</span>
        <span className="fa-text">{e.text || [e.cmd, e.by && `by ${e.by}`, e.what, e.reason].filter(Boolean).join(" ")}</span>
      </div>
    );
  return (
    <div className="fa-row" data-kind={e.kind} data-testid="fleet-text">
      {e.kind === "thinking" && <span className="fa-who mono">thinking</span>}
      <span className="fa-text">{last ? <Typed text={e.text || ""} live={live} fresh={!!e.ts && Date.now() / 1000 - Number(e.ts) < 4} /> : e.text}</span>
    </div>
  );
}

export function ThinkingView({ entries, live }: { entries: Entry[]; live: boolean }) {
  const rows = thinkingOf(entries);
  if (!rows.length) return <p className="muted fa-empty">Nothing written yet. Text and reasoning show here as they arrive.</p>;
  return (
    <div className="fa-list">
      {rows.map((e, i) => (
        <ThinkingRow key={i} e={e} last={i === rows.length - 1} live={live && i === rows.length - 1} />
      ))}
    </div>
  );
}

function fileOf(input: unknown): string {
  if (!input || typeof input !== "object") return "";
  const d = input as Record<string, unknown>;
  return String(d.file_path || d.path || d.notebook_path || "");
}

/** Edit / MultiEdit / Write as - / + lines. */
function Diff({ name, input }: { name: string; input: unknown }) {
  if (!input || typeof input !== "object") return null;
  const d = input as Record<string, unknown>;
  const pairs: [string, string][] = [];
  if (name === "Write" && typeof d.content === "string") pairs.push(["", d.content]);
  else if (typeof d.old_string === "string" || typeof d.new_string === "string") pairs.push([String(d.old_string || ""), String(d.new_string || "")]);
  else if (Array.isArray(d.edits)) for (const x of d.edits as Record<string, unknown>[]) pairs.push([String(x.old_string || ""), String(x.new_string || "")]);
  if (!pairs.length) return null;
  const lines = pairs.flatMap(([a, b]) => [...(a ? a.split("\n").map((l) => ["-", l]) : []), ...b.split("\n").map((l) => ["+", l])]).slice(0, 60);
  return (
    <pre className="fa-diff mono" data-testid="fleet-diff">
      {lines.map(([sign, l], i) => (
        <span key={i} className={sign === "+" ? "fa-add" : "fa-del"}>
          {sign} {l}
          {"\n"}
        </span>
      ))}
    </pre>
  );
}

function ToolRowView({ r }: { r: ToolRow }) {
  const [open, setOpen] = useState(false);
  const name = String(r.call.name || "?");
  const file = fileOf(r.call.input);
  const state = r.result ? (r.result.is_error ? "error" : "ok") : "running";
  const label = r.call.kind === "spawn" ? `${name}: ${r.call.task || ""}` : r.call.label || name;
  return (
    <div className="fa-tool" data-state={state} data-testid="fleet-tool-row">
      <button className="fa-tool-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name={r.call.kind === "spawn" ? "agent" : toolIcon(name) || "pulse"} size={14} />
        <span className="fa-tool-label mono">{label}</span>
        {file && <span className="og-chip mono fa-file" title={file}>{file.split(/[\\/]/).pop()}</span>}
        <span className="fa-tool-state mono">{state === "running" ? "running" : state === "error" ? "error" : "done"}</span>
      </button>
      {(open || state === "running") && <Diff name={name} input={r.call.input} />}
      {open && r.result && <pre className="fa-result mono">{(r.result.text || "").split("\n").slice(0, 14).join("\n")}</pre>}
      <span className="fa-when mono">{when(r.call.ts)}</span>
    </div>
  );
}

export function WorkingView({ entries }: { entries: Entry[] }) {
  const rows = workingOf(entries);
  if (!rows.length) return <p className="muted fa-empty">No tool call yet. Each one shows here with its arguments and result.</p>;
  return (
    <div className="fa-list">
      {rows.map((r, i) => (
        <ToolRowView key={String(r.call.id || i)} r={r} />
      ))}
    </div>
  );
}

export function OutputView({ entries, fallback, live }: { entries: Entry[]; fallback: string; live: boolean }) {
  const text = outputOf(entries) || fallback;
  if (!text) return <p className="muted fa-empty">No hand-back yet: its final answer shows here as it writes it.</p>;
  return (
    <div className="fa-output" data-testid="fleet-output">
      <Typed text={text} live={live} />
    </div>
  );
}
