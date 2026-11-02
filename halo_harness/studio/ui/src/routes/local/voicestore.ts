// Local -> Voice's store (3.3.9.0 R3; studio/voice_api.py + voice_act_api.py): the speech servers, the catalog, the
// devices, the sessions and the watched one's loop, the newest latency cards and `halo voice stats` (GET local/voice,
// on open and every REFRESH_MS while the page shows); the buttons (start / stop a server, download with its size line
// first, the loop on / off / ptt) said on their own row; Talk's turn (POST local/voice/talk, then its `talk` frames:
// the transcript, the reply's audio into the sink, the card). A selector never returns a fresh array.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { sess } from "../session/store";

export const REFRESH_MS = 15_000;

export type Finding = { id: string; rule: string; severity: string; finding: string; key: string; model: string };
export type VoiceServer = { kind: "stt" | "tts"; setting: string; model: string; running: boolean; url: string | null;
  device: string | null; remote: string | null; cost: string; bundle: string | null; findings: Finding[]; cli: string };
export type CatalogRow = { name: string; kind: string; engine: string; repo: string; download_gb: number; gpu_gb: number;
  cpu_gb: number; built: boolean; verified: boolean; note: string; present: string | null; size_line: string; cli: string };
export type Dev = { index: number; name: string; default: boolean };
export type Turn = { at: number; total_ms: number | null; budget_ms: number; line: string; via?: string; interrupted?: boolean };
export type Sess = { session_id: string; title: string; cwd: string; kind: string };
export type VoiceView = {
  servers: VoiceServer[]; catalog: CatalogRow[]; devices: { inputs: Dev[]; outputs: Dev[]; error: string | null };
  sessions: Sess[]; loop: { session: string; on: boolean; mode: string | null; lines: string[] }; turns: Turn[];
  stats: { turns: number; lines: string[] }; talk: { confirm: string; starts: string[]; max_s: number; rate: number };
  findings: Finding[]; cli: string;
};
export type TalkState = "idle" | "confirm" | "recording" | "sending" | "working" | "done" | "error";
export type Talk = { state: TalkState; job: string; transcript: string; reply: string; line: string; notes: string[];
  bytes: number; rate: number; error: string; seconds: number };
type Said = { ok: boolean; text: string };
type VoiceState = { view: VoiceView | null; error: string; session: string; busy: string; said: Record<string, Said>;
  confirm: Record<string, string>; talk: Talk; asked: boolean };

const IDLE: Talk = { state: "idle", job: "", transcript: "", reply: "", line: "", notes: [], bytes: 0, rate: 24000, error: "", seconds: 0 };
export const voice = createStore<VoiceState>({ view: null, error: "", session: "", busy: "", said: {}, confirm: {}, talk: IDLE,
  asked: false });

export function useVoice<S>(select: (s: VoiceState) => S): S {
  return useStore(voice, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const say = (k: string, s: Said) => voice.update((st) => ({ said: { ...st.said, [k]: s } }));
const lines = (r: { lines?: string[] }) => (r.lines || []).filter(Boolean).join(" · ");

/** The session Talk and the loop act on: the one chosen here, else Session's chosen one, else the first running. */
export function target(s: VoiceState): string {
  const rows = s.view?.sessions || [];
  const want = s.session || sess.get().chosen;
  return rows.find((r) => r.session_id === want)?.session_id || rows[0]?.session_id || "";
}

/** `withLoop`: ask the session's `/voice status` too (on open, a pick, a loop button -- not the 15 s refresh, which
 *  keeps the last answer: each ask is a line in that session's transcript). */
export async function loadVoice(withLoop = false): Promise<void> {
  try {
    const sid = target(voice.get());
    const view = await api.get<VoiceView>("local/voice", sid ? { session: sid, ...(withLoop ? { loop: 1 } : {}) } : undefined);
    const last = voice.get().view?.loop;
    voice.update(() => ({ view: !withLoop && last && sid ? { ...view, loop: last } : view, error: "" }));
  } catch (e) {
    voice.update(() => ({ error: msg(e) }));
  }
}

export function pickSession(id: string): void {
  voice.update(() => ({ session: id }));
  void loadVoice(true);
}

async function act(key: string, path: string, body: Record<string, unknown>): Promise<Record<string, unknown> | null> {
  voice.update(() => ({ busy: key }));
  try {
    const r = await api.post<Record<string, unknown>>(path, body);
    say(key, { ok: true, text: lines(r as { lines?: string[] }) });
    void loadVoice(key === "loop");
    return r;
  } catch (e) {
    say(key, { ok: false, text: msg(e) });
    return null;
  } finally {
    voice.update(() => ({ busy: "" }));
  }
}

export const server = (kind: string, op: "start" | "stop") => act(`server|${kind}`, "local/voice/server", { kind, op });
export const loop = (op: "on" | "off" | "ptt") => act("loop", "local/voice/loop", { session: target(voice.get()), op });

/** Download: the size line first (shown as the confirmation), then the 3.3.5.0 job on the second press. */
export async function download(model: string, yes = false): Promise<void> {
  const r = await act(`dl|${model}`, "local/voice/download", { model, yes });
  if (r && typeof r.confirm === "string") {
    voice.update((s) => ({ confirm: { ...s.confirm, [model]: yes ? "" : String(r.confirm) } }));
    if (yes) say(`dl|${model}`, { ok: true, text: `downloading ${String(r.confirm)} (the Hugging Face page shows its progress)` });
  }
}

export function cancelDownload(model: string): void {
  voice.update((s) => ({ confirm: { ...s.confirm, [model]: "" } }));
}

export function setTalk(patch: Partial<Talk>): void {
  voice.update((s) => ({ talk: { ...s.talk, ...patch } }));
}

export function resetTalk(state: TalkState = "idle"): void {
  voice.update(() => ({ talk: { ...IDLE, state } }));
}

/** Talk's utterance: 16-bit mono PCM at the browser's rate (the server resamples to the 16 kHz the stt hears). */
export async function sendTalk(pcm_b64: string, rate: number, seconds: number): Promise<void> {
  setTalk({ state: "sending", seconds });
  try {
    const r = await api.post<{ job: string }>("local/voice/talk", { pcm_b64, rate, session: target(voice.get()) });
    setTalk(voice.get().talk.state === "sending" ? { state: "working", job: r.job } : { job: r.job }); // its frames may come first
  } catch (e) {
    setTalk({ state: "error", error: msg(e) });
  }
}

type Frame = { job: string; state: string; text?: string; audio_b64?: string; rate?: number; transcript?: string;
  reply?: string; line?: string; bytes?: number; error?: string };
const sinks = new Set<(b64: string, rate: number) => void>();

/** The reply's audio as it arrives (VoiceTalk.tsx plays it and keeps it for the <audio> sink). */
export function onAudio(fn: (b64: string, rate: number) => void): () => void {
  sinks.add(fn);
  return () => {
    sinks.delete(fn);
  };
}

export function startVoiceFeed(): () => void {
  return onEvent("talk", (f) => {
    const d = (f.data || {}) as Frame;
    const t = voice.get().talk;
    if (!d.job || (t.job && d.job !== t.job)) return;
    if (d.state === "heard") setTalk({ transcript: d.text || "" });
    else if (d.state === "note" && d.text) setTalk({ notes: [...t.notes, d.text] });
    else if (d.state === "audio" && d.audio_b64) {
      setTalk({ bytes: d.bytes || t.bytes, rate: d.rate || t.rate });
      sinks.forEach((fn) => fn(d.audio_b64 || "", d.rate || 24000));
    } else if (d.state === "done") {
      setTalk({ state: "done", transcript: d.transcript || t.transcript, reply: d.reply || "", line: d.line || "", bytes: d.bytes ?? t.bytes });
      void loadVoice();
    } else if (d.state === "error") setTalk({ state: "error", error: d.error || "the turn stopped" });
  });
}
