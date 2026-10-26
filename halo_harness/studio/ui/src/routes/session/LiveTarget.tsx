// The Steer box's target line (3.3.0.0 R6, the owner: "you can't really tell
// which call you are steering"): "Steering: coder · Bash (pytest -q), 12 s"
// above the field -- the agent with its state glyph in its own colour, then
// what it does right now, from the feed: the tool it runs with what it runs
// on and for how long, else "thinking" while it works, "waiting on you",
// "paused", its end state, or "idle". When you change the target (a row, a
// node, Tab) it says what it was for a few seconds.
import { useEffect, useRef, useState } from "react";
import { short } from "../orchestra/format";
import { useNow } from "../fleet/store";
import { useLive, useOpenTool } from "../shared/liveFeed";
import { hueOf } from "../shared/hues";
import { GLYPH } from "./LiveRows";
import type { SteerTo } from "./steer";

const secs = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} m ${String(s % 60).padStart(2, "0")} s`;
};

/** What the agent does now, as the line says it. */
function useCall(t: SteerTo): string {
  const open = useOpenTool(t.key);
  const a = t.ref?.a;
  const running = a?.state === "running";
  const now = useNow(running && !!open, 1000);
  const arg = useLive((s) => {
    if (!open) return "";
    for (let i = s.lines.length - 1; i >= Math.max(0, s.lines.length - 400); i--) {
      const l = s.lines[i];
      if (l.key === t.key && l.kind === "tool" && !l.ended) return l.target || "";
    }
    return "";
  });
  if (running && open) {
    const cur = String(a?.current || "");
    const what = arg || (cur.startsWith(open.tool + ":") ? cur.slice(open.tool.length + 1).trim() : "");
    return `${open.tool}${what ? ` (${short(what, 60)})` : ""}, ${secs(now - open.t0)}`;
  }
  if (running) return "thinking";
  if (a?.state === "waiting") return "waiting on you";
  if (a?.state === "paused" || a?.state === "done" || a?.state === "failed" || a?.state === "stopped") return String(a.state);
  return "idle";
}

export function TargetLine({ t, name }: { t: SteerTo; name: string }) {
  const call = useCall(t);
  const state = String(t.ref?.a.state || "");
  const last = useRef({ key: t.key, name });
  const [was, setWas] = useState("");
  useEffect(() => {
    if (last.current.key === t.key) {
      last.current.name = name;
      return;
    }
    setWas(last.current.name);
    last.current = { key: t.key, name };
    const timer = window.setTimeout(() => setWas(""), 5000);
    return () => window.clearTimeout(timer);
  }, [t.key, name]);
  return (
    <div className="slv-target-line mono" data-testid="live-target" data-key={t.key} data-hc={hueOf(t.key)} data-state={state || undefined} aria-live="polite"
         title="Your steer goes to this agent; click a row or a map node, or press Tab in the field, to change it">
      <span className="rail-label">Steering:</span>
      <span className="slv-glyph" aria-hidden="true">{GLYPH[state] || "·"}</span>
      <span className="slv-target-name" data-testid="live-target-name">{name}</span>
      <span className="muted">·</span>
      <span className="slv-target-call" data-testid="live-target-call">{call}</span>
      {was && was !== name && <span className="muted slv-target-was" data-testid="live-target-was">(was {was})</span>}
    </div>
  );
}
