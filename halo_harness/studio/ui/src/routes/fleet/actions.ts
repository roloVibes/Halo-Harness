// What the live pieces do (Agents -> Live, Session): select, pin, follow, steer, pause, stop, shut a session down,
// pause / resume everything. Agent commands post to `live/<harness>/<sid>/agents/<aid>/command` ("local" for this
// harness), session commands to `live/<harness>/<sid>/command`.
import { api, ApiError } from "../../lib/api";
import { goSection, studio, toast } from "../../lib/store";
import { pickLive } from "../agents/live/scope";
import { roles } from "../roles/store";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";
import { scopedAgents } from "./scope";
import { append, follow, watch } from "./streams";
import { fleet, findAgent, findSession, isLive, parseKey, saveOpts, sessionTitle } from "./store";
import type { AgentKey, Harness } from "./types";
import { load } from "./sync";

const hidPath = (h: Harness | undefined, id: string) => (h?.local ? "local" : encodeURIComponent(id));

type Outcome = { ok: boolean; asked?: boolean; error?: string; result?: Record<string, unknown> };

async function post(path: string, body: Record<string, unknown>): Promise<Outcome> {
  try {
    const r = await api.post<{ ok?: boolean; asked?: boolean; text?: string; result?: Record<string, unknown> }>(path, body);
    if (r.asked) toast(r.text || "Waiting for that harness's owner to allow it", "info", 5000);
    return { ok: true, asked: !!r.asked, result: r.result };
  } catch (e) {
    const msg = e instanceof ApiError ? e.message : String(e);
    toast(msg, "error", 5000);
    return { ok: false, error: msg };
  }
}

export async function agentCommand(key: AgentKey, cmd: string, fields: Record<string, unknown> = {}): Promise<Outcome> {
  const { h, s, a } = parseKey(key);
  const ref = findAgent(fleet.get(), key);
  const out = await post(`live/${hidPath(ref?.h, h)}/${encodeURIComponent(s)}/agents/${encodeURIComponent(a)}/command`, { cmd, ...fields });
  window.setTimeout(() => void load(), 400);
  return out;
}

export async function sessionCommand(hid: string, sid: string, cmd: string, fields: Record<string, unknown> = {}): Promise<Outcome> {
  const got = findSession(fleet.get(), hid, sid);
  const out = await post(`live/${hidPath(got?.h, hid)}/${encodeURIComponent(sid)}/command`, { cmd, ...fields });
  window.setTimeout(() => void load(), 400);
  return out;
}

// -- selection, pin, follow -------------------------------------------------------
export function select(key: AgentKey): void {
  if (!key) return;
  fleet.update(() => ({ selected: key }));
  watch(key);
  if (studio.get().section === "agents") pickLive("agent", key); // 3.3.16.0 R2: Live's inspector says it (Activity's lane, a menu)
}

/** Double-click / Enter on a node: the agent's inspector, expanded and focused -- Session's Agent strip in Session, else
 *  (3.3.16.0 R2: the Fleet section went) Agents -> Live's inspector on the agent. */
export function openAgentPanel(key?: AgentKey): void {
  if (key) select(key);
  const k = key || fleet.get().selected;
  if (studio.get().section === "session") {
    if (layoutStore("session").get().layout) {
      patchPanel("session", "session-agent", { collapsed: false, face: "detail" }, false);
      focusPanel("session", "session-agent");
    }
    return;
  }
  if (k) pickLive("agent", k);
  if (studio.get().section !== "agents" || roles.get().canvasView !== "live") goSection("agents", "live");
  if (layoutStore("roles").get().layout) {
    patchPanel("roles", "roles-inspector", { collapsed: false, face: "detail" }, false);
    focusPanel("roles", "roles-inspector");
  }
}

export function pin(key: AgentKey | "" = fleet.get().selected): void {
  const was = fleet.get().pinned;
  fleet.update(() => ({ pinned: key }));
  if (key) {
    watch(key);
    toast("Pinned: its mini stream stays on screen (Esc unpins)", "info", 2600);
  } else if (was && was !== fleet.get().selected) void follow(was, false);
}

export function toggleFollow(): void {
  fleet.update((s) => ({ follow: !s.follow }));
  saveOpts();
  toast(fleet.get().follow ? "Follow on: the stream scrolls with the agent" : "Follow off", "info", 2000);
}

/** J / K: the next (or previous) live agent in scope; every agent when none is live. */
export function hop(dir: 1 | -1): void {
  const s = fleet.get();
  const all = scopedAgents(s);
  const live = all.filter((r) => isLive(r.a));
  const list = live.length ? live : all;
  if (!list.length) return;
  const i = list.findIndex((r) => r.key === s.selected);
  const n = list.length;
  select(list[i < 0 ? (dir > 0 ? 0 : n - 1) : (i + dir + n) % n].key);
}

// -- the agent commands ------------------------------------------------------------
export async function steer(key: AgentKey, text: string, mode: "nudge" | "redirect"): Promise<boolean> {
  const t = text.trim();
  if (!key || !t) return false;
  append(key, { kind: "user", text: t, tag: "steer", mode, you: true, ts: Date.now() / 1000 });
  const r = await agentCommand(key, "steer", { text: t, mode });
  if (r.ok && !r.asked) toast(mode === "redirect" ? "Redirected: it reads the new task before its next step" : "Steered: it reads it before its next step", "done");
  return r.ok;
}

export async function togglePause(key: AgentKey = fleet.get().selected): Promise<void> {
  const ref = findAgent(fleet.get(), key);
  if (!ref) return;
  const paused = ref.a.state === "paused";
  const r = await agentCommand(key, paused ? "resume" : "pause");
  if (r.ok && !r.asked) toast(paused ? "Resumed" : "Paused: it holds at its next tool or model call", "done");
}

/** Stop and Shutdown ask first (the confirm dialog, FleetDialogs). */
export function askStop(key: AgentKey = fleet.get().selected): void {
  const ref = findAgent(fleet.get(), key);
  if (ref) fleet.update(() => ({ confirm: { what: "stop", key, label: ref.a.name || ref.a.agent_id } }));
}

export function askShutdown(hid: string, sid: string): void {
  const got = findSession(fleet.get(), hid, sid);
  if (got) fleet.update(() => ({ confirm: { what: "shutdown", key: `${hid}|${sid}|main`, label: sessionTitle(got.s) } }));
}

export async function confirmed(): Promise<void> {
  const c = fleet.get().confirm;
  fleet.update(() => ({ confirm: null }));
  if (!c) return;
  if (c.what === "stop") {
    const r = await agentCommand(c.key, "stop", { reason: "stopped from Studio" });
    if (r.ok && !r.asked) toast(`${c.label}: stopping at its next step`, "done");
  } else {
    const { h, s } = parseKey(c.key);
    const r = await sessionCommand(h, s, "shutdown", { reason: "shut down from Studio" });
    if (r.ok && !r.asked) toast(`${c.label}: shutting down after the current tool call`, "done");
  }
}

export async function everySession(cmd: "pause" | "resume"): Promise<void> {
  const targets = fleet.get().harnesses.flatMap((h) => (h.allow_control === "none" ? [] : h.sessions.map((s) => [h.id, s.session_id] as const)));
  if (!targets.length) {
    toast("No session to " + cmd, "info");
    return;
  }
  const results = await Promise.all(targets.map(([h, s]) => sessionCommand(h, s, cmd)));
  const ok = results.filter((r) => r.ok).length;
  toast(`${cmd === "pause" ? "Paused" : "Resumed"} ${ok} of ${targets.length} session${targets.length === 1 ? "" : "s"}`, ok ? "done" : "error");
}
