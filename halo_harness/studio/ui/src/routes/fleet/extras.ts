// What the live panels do: answer an attention row with one key
// (`POST live/attention/answer`; `o` only says where to open it), take an
// agent over or hand it on as a written brief (`.../agents/<aid>/handoff`),
// record a session or one agent (`.../recording[?agent=]`, then the file is
// fetched with the token header and saved as a blob), set the spend caps.
import { api, ApiError, token } from "../../lib/api";
import { goSection, toast, type SectionId } from "../../lib/store";
import { openLocalHost, showFleetPanel } from "../agents/fleetDoor";
import { select } from "./actions";
import { fleet, findAgent, findSession, parseKey, sessionTitle } from "./store";
import { load } from "./sync";
import { loadAttention, loadConflicts, loadCosts } from "./pload";
import { openRun } from "../agents/run/door";
import { reviewPlan } from "../agents/run/planPanel";
import { closeDialog, openDialog, panels, type AttnRow, type CapKey, type HandoffOut, type OpenTarget } from "./pstore";

export { showFleetPanel }; // 3.3.16.0 R2: an old Fleet panel's door opens its new home (routes/agents/fleetDoor.ts)

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const hidPath = (hid: string) => (fleet.get().harnesses.find((h) => h.id === hid)?.local ? "local" : encodeURIComponent(hid));

/** Where an `o` answer points: a section and view; a live row (section `live`, 3.5.0.0; `fleet` before) its home --
 *  the steward's note Local -> Hosts on its host, an agent or a conflict Live on it, a cap Agents' Attention. */
export function openTarget(t: OpenTarget): void {
  if (t.section !== "live" && t.section !== "fleet") {
    if (t.run && !t.stage && (t.view === "runs" || t.view === "live")) return void openRun(t.run); // 3.4.0.0 D: on Live while it runs, else History
    goSection(t.section as SectionId, t.view === "runs" ? "live" : t.view); // 3.3.16.0 R1: a row of `orchestra` or `roles` opens Agents on its view
    if (t.panel === "orchestra-plan") reviewPlan(); // the supervisor's "open the plan"
    return;
  }
  if (t.panel === "ollama" || t.panel === "fleet-ollama") return openLocalHost(t.host || ""); // 3.3.4.0 R5: the steward's attention row
  const aid = t.a ? t.a.split("|")[2] : t.agent_id || "main";
  if (t.a) select(t.a);
  else if (t.harness && t.session_id) select(`${t.harness}|${t.session_id}|${aid}`);
  showFleetPanel(t.a || t.session_id ? "fleet-agent" : t.panel || "fleet-agent");
}

export async function answerRow(row: AttnRow, key: string, text = ""): Promise<boolean> {
  try {
    const r = await api.post<{ ok?: boolean; answer?: string; open?: OpenTarget; set_aside?: boolean; lifted?: boolean }>("live/attention/answer", { id: row.id, key, ...(text ? { text } : {}) });
    if (r.open) openTarget(r.open); // `o`
    else toast(`${row.what}: ${r.answer || row.keys[key] || key}`, "done");
    panels.update((s) => ({ replyFor: "", attention: r.open ? s.attention : s.attention.filter((x) => x.id !== row.id) }));
    window.setTimeout(() => (void loadAttention(), void load()), 400);
    if (row.kind === "cap") window.setTimeout(() => void loadCosts(), 600);
    if (row.kind === "conflict") window.setTimeout(() => void loadConflicts(), 600);
    return true;
  } catch (e) {
    toast(msg(e), "error", 5000);
    void loadAttention();
    return false;
  }
}

// -- hand-offs ---------------------------------------------------------------------------------
export function askHandoff(kind: "take_over" | "hand_to", key = fleet.get().selected): void {
  const ref = findAgent(fleet.get(), key);
  if (!ref) {
    toast("Pick an agent first (click it on the map)", "info");
    return;
  }
  openDialog(kind === "take_over" ? { kind, key, label: ref.a.name || ref.a.agent_id } : { kind, key, label: ref.a.name || ref.a.agent_id });
}

export async function handoff(key: string, body: { mode: "take_over"; brief: string } | { mode: "hand_to"; to: string; brief?: string }): Promise<boolean> {
  const { h, s, a } = parseKey(key);
  const label = findAgent(fleet.get(), key)?.a.name || a;
  try {
    const out = await api.post<HandoffOut>(`live/${hidPath(h)}/${encodeURIComponent(s)}/agents/${encodeURIComponent(a)}/handoff`, body);
    if (body.mode === "take_over") {
      closeDialog();
      toast(`${label}: taken over, it reads your brief before its next step`, "done");
    } else openDialog({ kind: "handed", label, out });
    window.setTimeout(() => void load(), 500);
    return true;
  } catch (e) {
    toast(msg(e), "error", 6000);
    return false;
  }
}

// -- recordings ------------------------------------------------------------------------------------
export async function record(key: string, agentOnly: boolean): Promise<void> {
  const { h, s, a } = parseKey(key);
  const got = findSession(fleet.get(), h, s);
  const label = agentOnly ? findAgent(fleet.get(), key)?.a.name || a : got ? sessionTitle(got.s) : s.slice(0, 8);
  toast(`Recording ${label}...`, "info", 2000);
  try {
    const r = await api.post<{ name: string; url: string; bytes: number }>(`live/${hidPath(h)}/${encodeURIComponent(s)}/recording`, {}, agentOnly ? { agent: a } : undefined);
    openDialog({ kind: "recording", name: r.name, url: r.url, bytes: r.bytes, label });
  } catch (e) {
    toast(msg(e), "error", 6000);
  }
}

/** The recording route wants the token header, so the file is fetched and saved as a blob. */
export async function download(url: string, name: string): Promise<boolean> {
  try {
    const res = await fetch(new URL("api/" + url, location.origin + "/"), { headers: { Authorization: "Bearer " + token() } });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const blob = await res.blob();
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = name;
    link.dataset.testid = "fleet-recording-link";
    document.body.appendChild(link);
    link.click();
    window.setTimeout(() => (URL.revokeObjectURL(href), link.remove()), 1000);
    toast(`Saved ${name} (${Math.round(blob.size / 1024)} KB): open it in any browser, it needs no network`, "done", 4000);
    return true;
  } catch (e) {
    toast(`The recording did not download: ${msg(e)}`, "error", 6000);
    return false;
  }
}

// -- caps -------------------------------------------------------------------------------------------
export async function saveCaps(values: Partial<Record<CapKey, number | null>>): Promise<boolean> {
  try {
    await api.post("live/caps", values);
    toast("Caps saved", "done");
    void loadCosts();
    return true;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return false;
  }
}
