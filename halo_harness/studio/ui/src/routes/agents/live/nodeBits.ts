// What an agent node says (3.3.16.0 R2: moved here from the Fleet Map's MapNode.tsx / MapTreeNode.tsx when the Map
// went; Agents -> Live's node, Session's Map, the Agent panel's glance and Session's Cost read them): what it does now,
// a cost that counts up to its value (the ticker), and the running tool with how long it has run ("Bash 12s", from the
// feed: shared/liveFeed.ts).
import { useEffect, useRef, useState } from "react";
import { startLive, useOpenTool } from "../../shared/liveFeed";
import { toolOf, useNow } from "../../fleet/store";
import type { Activity, AgentRow, SessionRow } from "../../fleet/types";

/** A session's project: the repo (or folder) and its branch, `*` when dirty (the session node, People's row). */
export function projectLabel(s: SessionRow): string {
  const p = s.project || {};
  const name = String(p.repo || p.root || s.cwd || "").replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "no project";
  return p.branch ? `${name} · ${p.branch}${p.dirty ? "*" : ""}` : name;
}

/** One line: what the agent does now (waits on you, paused, queued, its tool, how it ended, else its task). */
export function nowText(a: AgentRow): string {
  if (a.state === "waiting") return "waits on you";
  if (a.state === "paused") return "paused: holds at its next step";
  if (a.state === "queued") return "queued";
  if (a.current) return a.current;
  if (a.state === "done" || a.state === "failed" || a.state === "stopped") return `${a.state}${a.last_text ? ": " + a.last_text : ""}`;
  return a.task || "";
}

/** A number that counts up to `value` over ~600 ms (the cost ticker). */
export function useTicker(value: number): number {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    if (value <= a) {
      from.current = value;
      setShown(value);
      return;
    }
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / 600);
      setShown(a + (value - a) * k);
      if (k < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return shown;
}

/** "Bash 12s" while a tool runs (its start seen on the feed), "Bash" when only the row says so, "" when none. */
export function useToolClock(key: string, a: AgentRow | undefined, act: Activity | undefined): { tool: string; text: string; secs: number | null } {
  useEffect(() => startLive(), []);
  const open = useOpenTool(key);
  const running = a?.state === "running";
  const now = useNow(running && !!open, 1000);
  const tool = running ? open?.tool || toolOf(a, act) : "";
  if (!tool) return { tool: "", text: "", secs: null };
  const secs = open ? Math.max(0, Math.round((now - open.t0) / 1000)) : null;
  const clock = secs == null ? "" : secs < 60 ? ` ${secs}s` : ` ${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, "0")}s`;
  return { tool, text: tool + clock, secs };
}
