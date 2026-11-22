// What the Prompt panel sends (3.3.11.0 R1), all to this harness's session over its control socket
// (POST sessions/<sid>/command, studio/sessions_prompt_api.py):
// * a line starting with `/` (one line) is `slash`: its output comes back as the lines the TUI would print;
// * a one-line `!command` is `slash` too (3.6.0.12 BS), busy or not, an image chip or not (the chip waits for the
//   next prompt, as the terminal's does): the session runs it as its
//   terminal does (no turn, no receipt) and the panel's answer line says ran / asks first / denied / still running;
// * anything else is `submit` with `when_busy: refuse` and a fresh `client_id` (the receipt's idempotency key: a
//   retry of the same send returns the stored row, never a second turn). Told the session is busy, the panel
//   keeps the text and offers Queue it (`when_busy: queue`: it starts when the running turn ends; one at a time,
//   a second answers 409 with the line) or Steer (`when_busy: steer`: it lands in the running turn);
// * an ask's button is `answer` (the socket's: permission, question, plan, approval) with its own receipt.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { imageFields } from "./steerImage";
// 3.6.0.2 P72: the box changes only when the answer to a send arrives, and then only for a send that was taken
// (promptDraft.ts takeSent, given the text this answer took); P22: a steer's row is drawn once (steerSent / steerAnswered); P23: an answered ask reads
// `Answered in Studio: <label>` with the label from THE table (promptWords.ts askLabel).
import { dropSent, pushHistory, recordSent, takeSent } from "./promptDraft";
import { addOut, loadReceipts, noteReceipt, prompt, steerAnswered, steerSent, type Receipt } from "./promptStore";
import { answeredLine, askLabel, bangLines, routeOf, type BangAnswer } from "./promptWords";

type Answer = { ok?: boolean; busy?: boolean; held?: boolean; line?: string; duplicate?: boolean; receipt?: Receipt;
  result?: Record<string, unknown>; error?: string };

let cid = 0;
/** A fresh idempotency key for one send. */
export const clientId = (): string => `pp-${Date.now().toString(36)}-${(++cid).toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

async function post(sid: string, body: Record<string, unknown>): Promise<{ status: number; data: Answer }> {
  try {
    return { status: 200, data: await api.post<Answer>(`sessions/${encodeURIComponent(sid)}/command`, body) };
  } catch (e) {
    if (e instanceof ApiError) return { status: e.status, data: { ...(e.data as Answer), error: e.message } };
    return { status: 0, data: { error: String(e) } };
  }
}

/** A `/command` line: run it in the session, its output as lines here. */
export async function runSlash(sid: string, line: string): Promise<boolean> {
  prompt.update(() => ({ sending: true }));
  const r = await post(sid, { cmd: "slash", line });
  prompt.update(() => ({ sending: false }));
  const result = (r.data.result || {}) as { lines?: string[]; output?: string; ran?: boolean };
  if (r.status !== 200) {
    dropSent();
    addOut(sid, line, [r.data.error || "the session did not answer"], true);
    return false;
  }
  pushHistory(sid, line);
  if (line.startsWith("!")) { // 3.6.0.12 BS: the answer line; a denied one stays in the box, an ask runs on its Allow
    addOut(sid, line, bangLines(result as BangAnswer));
    if ((result as BangAnswer).state === "denied") dropSent();
    else takeSent(line);
    return true;
  }
  const lines = Array.isArray(result.lines) ? result.lines : String(result.output || "").split(/\r?\n/);
  addOut(sid, line, lines.length && lines.some((l) => l.trim()) ? lines : ["(no output: the command ran, or became the next turn)"]);
  if (result.ran === false) dropSent(); // nothing ran: the line stays in the box
  else takeSent(line);
  return true;
}

/** 3.6.0.12 BS: Stop on a running `!` command's row: the session's `interrupt`, what Esc does in the terminal. */
export async function stopBang(sid: string): Promise<void> {
  const r = await post(sid, { cmd: "interrupt" });
  if (r.status !== 200) toast(r.data.error || "the session did not take the Stop", "error", 6000);
}

/** Submit `text` with `when` (refuse first); the chip's image rides with it. True when the session took it. */
export async function submit(sid: string, text: string, when: "refuse" | "queue" | "steer"): Promise<boolean> {
  const img = prompt.get().img;
  prompt.update(() => ({ sending: true }));
  if (when === "steer") steerSent(sid, text);
  const r = await post(sid, { cmd: "submit", text, when_busy: when, client_id: clientId(), ...(img ? imageFields(img) : {}) });
  prompt.update(() => ({ sending: false }));
  noteReceipt(r.data.receipt);
  if (when === "steer") steerAnswered(r.status === 200 && !!(r.data.result || {}).steered, r.data.receipt?.id || "");
  if (r.status === 200 && r.data.busy && !(r.data.result || {}).queued) {
    prompt.update(() => ({ busy: { sid, text, line: r.data.line || "A turn is running." } })); // the record waits for Queue it / Steer
    return false;
  }
  if (r.status !== 200) { // the box is left as it is; the record stays for a Steer or Queue it sent again
    toast(r.data.error || "the session did not take it", r.status === 409 ? "info" : "error", 6000);
    if (r.status === 409) (dropSent(), prompt.update(() => ({ busy: null })));
    return false;
  }
  const queued = !!(r.data.result || {}).queued;
  prompt.update(() => ({ busy: null }));
  takeSent(text);
  pushHistory(sid, text);
  if (queued) toast("Queued: it starts when the running turn ends", "done");
  else if ((r.data.result || {}).steered) toast("Steered: it lands in the running turn", "done");
  void loadReceipts(sid);
  return true;
}

/** Enter in the box: a slash line runs, anything else is a turn (refused while busy, then the choice). */
export async function send(sid: string, raw: string): Promise<boolean> {
  const text = raw.replace(/\s+$/, "");
  if (!sid || (!text.trim() && !prompt.get().img) || prompt.get().sending) return false;
  if (routeOf(text, !!prompt.get().img) === "slash") { // a `/` or `!` line, busy or not (promptWords.ts)
    recordSent(text, null);
    return runSlash(sid, text.trim());
  }
  recordSent(text, prompt.get().img);
  return submit(sid, text, "refuse");
}

/** The busy line's buttons: Queue it, Steer (the held text goes); Cancel keeps the text in the box. */
export async function resolveBusy(how: "queue" | "steer" | "cancel"): Promise<boolean> {
  const b = prompt.get().busy;
  if (!b) return false;
  if (how === "cancel") {
    dropSent();
    prompt.update(() => ({ busy: null }));
    return false;
  }
  return submit(b.sid, b.text, how);
}

/** An ask's button: the socket's `answer` with its fields; the card's one line says what you chose (P23). */
export async function answer(sid: string, kind: string, id: string, fields: Record<string, unknown>, card = id): Promise<boolean> {
  const r = await post(sid, { cmd: "answer", kind, request_id: id, client_id: clientId(), ...fields });
  noteReceipt(r.data.receipt);
  if (r.status !== 200) {
    toast(r.data.error || "the session did not take the answer", "error", 6000);
    return false;
  }
  prompt.update((s) => ({ answered: { ...s.answered, [card]: answeredLine("studio", askLabel(kind, fields)) } }));
  void loadReceipts(sid);
  return true;
}
