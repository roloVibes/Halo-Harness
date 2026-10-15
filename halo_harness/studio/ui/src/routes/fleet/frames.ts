// Live Roles: the shell <-> the framed Roles and Org pages (static/legacy/
// live.js), postMessage on this origin only. The shell posts
// `{type: "fleet-live", agents}` -- every live agent (and one that just
// finished) with what it is doing right now -- on every change, and
// `{type: "fleet-stream", key, entries}` for the agent a frame's Live tab
// shows. The frame asks: `fleet-ready`, `fleet-watch {key}`, `fleet-command
// {id, key, cmd, text?, mode?}`, `fleet-history {id, role, bio}`, `fleet-pin
// {key}`; answers come back as `fleet-result {id, ok, ...}`. The frame never
// calls the fleet routes itself: the shell proxies every one.
import { useEffect } from "react";
import { api, ApiError } from "../../lib/api";
import { short } from "../orchestra/format";
import { agentCommand, pin, select, steer } from "./actions";
import { allAgents, fleet, isLive, sessionTitle, toolOf, type FleetState } from "./store";
import { startFleet } from "./sync";
import type { AgentRef } from "./types";

export type LiveRow = {
  key: string; harness: string; local: boolean; session: string; session_id: string; agent_id: string; parent: string | null;
  name: string; role: string; bio: string; lineup: string; model: string; state: string; task: string; current: string;
  last_text: string; cost_usd: number; since: number; activity: string; tool: string; calls: number; control: string;
};

const RECENT_MS = 3000;
const ACT_MS = 4000;

/** typing | tool | waiting | working | queued | done | failed: the card's glow (live.css). */
function activityOf(r: AgentRef, s: FleetState, now: number): string {
  const st = String(r.a.state || "");
  const act = s.activity[r.key];
  if (st === "waiting" || st === "paused") return "waiting";
  if (st === "failed") return "failed";
  if (st === "done" || st === "stopped") return "done";
  if (st === "queued") return "queued";
  if (act && now - act.ts < ACT_MS) return act.kind;
  return r.a.current && r.a.current !== "thinking" ? "tool" : "typing";
}

export function liveRows(s: FleetState): LiveRow[] {
  const now = Date.now();
  return allAgents(s)
    .filter((r) => isLive(r.a) || now - (s.doneAt[r.key] || 0) < RECENT_MS)
    .map((r) => ({
      key: r.key, harness: r.h.name || r.h.id.slice(0, 8), local: !!r.h.local, session: sessionTitle(r.s),
      session_id: r.s.session_id, agent_id: r.a.agent_id, parent: r.a.parent || null, name: r.a.name || r.a.agent_id,
      role: r.a.role || "", bio: r.a.bio || "", lineup: r.a.lineup || "", model: r.a.model || "", state: String(r.a.state || ""),
      task: r.a.task || "", current: r.a.current || "", last_text: short(r.a.last_text, 160), cost_usd: Number(r.a.cost_usd) || 0,
      since: Number(r.a.since) || 0, activity: activityOf(r, s, now), tool: toolOf(r.a, s.activity[r.key]),
      calls: s.activity[r.key]?.calls || 0, control: r.h.allow_control || "all",
    }));
}

type Ask = { type?: string; id?: number; key?: string; cmd?: string; text?: string; mode?: string; role?: string; bio?: string };

async function answer(d: Ask): Promise<Record<string, unknown>> {
  const key = String(d.key || "");
  if (d.type === "fleet-history") {
    try {
      const r = await api.get<{ runs: unknown[] }>("fleet/history", { role: d.role || "", bio: d.bio || "", n: 12 });
      return { ok: true, runs: r.runs };
    } catch (e) {
      return { ok: false, error: e instanceof ApiError ? e.message : String(e) };
    }
  }
  if (d.cmd === "steer") return { ok: await steer(key, String(d.text || ""), d.mode === "redirect" ? "redirect" : "nudge") };
  if (["pause", "resume", "stop"].includes(String(d.cmd))) {
    const r = await agentCommand(key, String(d.cmd), d.cmd === "stop" ? { reason: "stopped from Studio (Roles)" } : {});
    return { ok: r.ok, asked: r.asked, error: r.error };
  }
  return { ok: false, error: `unknown command ${d.cmd}` };
}

export function useFleetFrames(): void {
  useEffect(() => {
    let last = "";
    let timer = 0;
    const watching = new Map<Window, string>();
    const sent = new Map<Window, number>();
    const frames = () =>
      Array.from(document.querySelectorAll<HTMLIFrameElement>("iframe.legacy-frame"))
        .map((f) => f.contentWindow)
        .filter((w): w is Window => !!w);
    const send = (w: Window, msg: unknown) => {
      try {
        w.postMessage(msg, location.origin);
      } catch {
        /* a frame mid-navigation */
      }
    };
    const pushLive = () => {
      const msg = { type: "fleet-live", agents: liveRows(fleet.get()), pinned: fleet.get().pinned };
      const json = JSON.stringify(msg);
      if (json === last) return;
      last = json;
      frames().forEach((w) => send(w, msg));
    };
    const pushStreams = () => {
      for (const [w, key] of watching) {
        const st = fleet.get().streams[key];
        if (!key || sent.get(w) === (st?.tick ?? -1)) continue;
        sent.set(w, st?.tick ?? -1);
        send(w, { type: "fleet-stream", key, entries: (st?.entries || []).slice(-120), loading: !!st?.loading, error: st?.error || "" });
      }
    };
    const unsub = fleet.subscribe(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => (pushLive(), pushStreams()), 120);
    });
    const tick = window.setInterval(() => pushLive(), 1000); // a done sweep or a typing glow ages out
    const onMsg = async (e: MessageEvent) => {
      if (e.origin !== location.origin || !e.data || typeof e.data !== "object") return;
      const w = e.source as Window | null;
      const d = e.data as Ask;
      if (!w || !String(d.type || "").startsWith("fleet-") || !frames().includes(w)) return;
      if (d.type === "fleet-ready") {
        startFleet();
        send(w, { type: "fleet-live", agents: liveRows(fleet.get()), pinned: fleet.get().pinned });
      } else if (d.type === "fleet-watch") {
        watching.set(w, String(d.key || ""));
        sent.delete(w);
        if (d.key) select(d.key);
        pushStreams();
      } else if (d.type === "fleet-pin") pin(String(d.key || ""));
      else if (d.type === "fleet-command" || d.type === "fleet-history") send(w, { type: "fleet-result", id: d.id, ...(await answer(d)) });
    };
    window.addEventListener("message", onMsg);
    return () => {
      unsub();
      window.clearInterval(tick);
      window.clearTimeout(timer);
      window.removeEventListener("message", onMsg);
    };
  }, []);
}
