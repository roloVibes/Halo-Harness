// What the Prompt panel sends (3.3.11.0 R1), all to this harness's session over its control socket
// (POST sessions/<sid>/command, studio/sessions_prompt_api.py):
// * a line starting with `/` (one line) is `slash`: its output comes back as the lines the TUI would print;
// * anything else is `submit` with `when_busy: refuse` and a fresh `client_id` (the receipt's idempotency key: a
//   retry of the same send returns the stored row, never a second turn). Told the session is busy, the panel
//   keeps the text and offers Queue it (`when_busy: queue`: it starts when the running turn ends; one at a time,
//   a second answers 409 with the line) or Steer (`when_busy: steer`: it lands in the running turn);
// * an ask's button is `answer` (the socket's: permission, question, plan, approval) with its own receipt.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { imageFields } from "./steerImage";
import { addOut, loadReceipts, noteReceipt, prompt, pushHistory, type Receipt } from "./promptStore";

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
  const result = (r.data.result || {}) as { lines?: string[]; output?: string };
  if (r.status !== 200) {
    addOut(sid, line, [r.data.error || "the session did not answer"], true);
    return false;
  }
  const lines = Array.isArray(result.lines) ? result.lines : String(result.output || "").split(/\r?\n/);
  addOut(sid, line, lines.length && lines.some((l) => l.trim()) ? lines : ["(no output: the command ran, or became the next turn)"]);
  pushHistory(sid, line);
  return true;
}

/** Submit `text` with `when` (refuse first); the chip's image rides with it. True when the session took it. */
export async function submit(sid: string, text: string, when: "refuse" | "queue" | "steer"): Promise<boolean> {
  const img = prompt.get().img;
  prompt.update(() => ({ sending: true }));
  const r = await post(sid, { cmd: "submit", text, when_busy: when, client_id: clientId(), ...(img ? imageFields(img) : {}) });
  prompt.update(() => ({ sending: false }));
  noteReceipt(r.data.receipt);
  if (r.status === 200 && r.data.busy && !(r.data.result || {}).queued) {
    prompt.update(() => ({ busy: { sid, text, line: r.data.line || "A turn is running." } }));
    return false;
  }
  if (r.status !== 200) {
    toast(r.data.error || "the session did not take it", r.status === 409 ? "info" : "error", 6000);
    if (r.status === 409) prompt.update(() => ({ busy: null }));
    return false;
  }
  const queued = !!(r.data.result || {}).queued;
  prompt.update(() => ({ busy: null, img: null, imgError: "", draft: "" }));
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
  if (text.startsWith("/") && !text.includes("\n") && !prompt.get().img) {
    const ok = await runSlash(sid, text.trim());
    if (ok) prompt.update(() => ({ draft: "" }));
    return ok;
  }
  return submit(sid, text, "refuse");
}

/** The busy line's buttons: Queue it, Steer (the held text goes); Cancel keeps the text in the box. */
export async function resolveBusy(how: "queue" | "steer" | "cancel"): Promise<boolean> {
  const b = prompt.get().busy;
  if (!b) return false;
  if (how === "cancel") {
    prompt.update(() => ({ busy: null }));
    return false;
  }
  return submit(b.sid, b.text, how);
}

/** An ask's button: the socket's `answer` with its fields; the card says what you chose. */
export async function answer(sid: string, kind: string, id: string, label: string, fields: Record<string, unknown>, card = id): Promise<boolean> {
  const r = await post(sid, { cmd: "answer", kind, request_id: id, client_id: clientId(), ...fields });
  noteReceipt(r.data.receipt);
  if (r.status !== 200) {
    toast(r.data.error || "the session did not take the answer", "error", 6000);
    return false;
  }
  prompt.update((s) => ({ answered: { ...s.answered, [card]: label } }));
  void loadReceipts(sid);
  return true;
}
