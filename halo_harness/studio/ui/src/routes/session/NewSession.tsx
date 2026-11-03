// A session with no terminal (3.3.11.0 R2): Studio's server starts `halo --headless --session-for studio` as a
// child (studio/sessions_new_api.py) -- the same loop and session log as the TUI, its control socket the only
// door. The Start view and the Prompt panel (with no session here) show the form: the model (the Setup
// default-model block's rows: GET sessions/new, the configured catalog, the default first) and the working
// folder (Studio's by default). Start answers with the session id; Session opens on it with the Prompt focused.
// Closing the tab never ends it: the Prompt panel's "End session" does (`shutdown`), and "Open in terminal"
// copies the `halo --resume <id>` line that opens it in a terminal later.
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { Button } from "../../lib/ui";
import { fleet } from "../fleet/store";
import { load as loadFleet } from "../fleet/sync";
import type { SessionRow } from "../fleet/types";
import { openPrompt } from "./promptStore";
import { localSessions, openSession } from "./store";

type ModelOpt = { ref: string; label?: string | null; provider?: string | null; price?: string | null };
type NewInfo = { model: string; cwd: string; models: ModelOpt[] };
type Started = { session_id: string; pid: number; cwd: string; model: string; resume: string };

export const resumeLine = (s: { session_id: string; cwd?: string | null }) =>
  `halo${s.cwd ? ` --cwd "${s.cwd}"` : ""} --resume ${s.session_id}`;

/** Once the box is on the page (the workspace replaces the Start view when the session registers), open the
 *  Prompt again: the panel takes its pending focus first, then the box (the R1 `--prompt` path). */
function whenBoxShows(tries = 100): void {
  if (document.querySelector('[data-testid="prompt-input"]:not([disabled])') || tries <= 0) openPrompt();
  else window.setTimeout(() => whenBoxShows(tries - 1), 100);
}

/** The keyboard into the Prompt box once the new session is listed (the box takes no keys before). */
function focusWhenListed(sid: string): void {
  let done = false;
  const off = fleet.subscribe(() => {
    if (done || !localSessions(fleet.get()).some((x) => x.session_id === sid)) return;
    done = true;
    off();
    window.setTimeout(() => whenBoxShows(), 80);
  });
  window.setTimeout(() => (done = true, off()), 120_000);
}

/** Start one; Session opens on it (it registers a moment later), the Prompt focused. */
export async function startNew(model: string, cwd: string): Promise<Started> {
  const r = await api.post<Started>("sessions/new", { model, cwd });
  openSession({ session: r.session_id });
  openPrompt();
  focusWhenListed(r.session_id);
  toast(`Started a session with no terminal (${r.session_id.slice(0, 8)}): it shows here the moment it registers`, "done", 5000);
  window.setTimeout(() => void loadFleet(), 1500);
  return r;
}

export function NewSession({ compact }: { compact?: boolean }) {
  const [info, setInfo] = useState<NewInfo | null>(null);
  const [model, setModel] = useState("");
  const [cwd, setCwd] = useState("");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState("");
  useEffect(() => {
    api.get<NewInfo>("sessions/new").then(setInfo, (e) => setSaid(e instanceof Error ? e.message : String(e)));
  }, []);
  const groups = useMemo(() => {
    const out = new Map<string, ModelOpt[]>();
    for (const m of info?.models || []) out.set(m.provider || "other", [...(out.get(m.provider || "other") || []), m]);
    return [...out.entries()];
  }, [info]);
  const go = async () => {
    setBusy(true);
    setSaid("");
    try {
      await startNew(model, cwd);
    } catch (e) {
      setSaid(e instanceof ApiError ? e.problems[0] || e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ss-new" data-testid="session-new" data-compact={compact || undefined}>
      {!compact && <div className="rail-label mono">NEW SESSION · NO TERMINAL</div>}
      <label className="ss-new-row">
        <span className="mono muted">model</span>
        <select className="input mono" value={model} onChange={(e) => setModel(e.target.value)} disabled={!info} data-testid="session-new-model">
          <option value="">{info?.model ? `the default: ${info.model}` : "the default model"}</option>
          {groups.map(([provider, list]) => (
            <optgroup key={provider} label={provider}>
              {list.map((m) => <option key={m.ref} value={m.ref}>{m.ref}{m.price && m.price !== "?" ? ` · ${m.price}` : ""}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      <label className="ss-new-row">
        <span className="mono muted">folder</span>
        <input className="input mono" value={cwd} onChange={(e) => setCwd(e.target.value)} placeholder={info?.cwd || "Studio's folder"}
               onKeyDown={(e) => e.key === "Enter" && !busy && void go()} aria-label="The working folder" data-testid="session-new-cwd" />
      </label>
      <div className="ss-new-row">
        <Button size="sm" variant="primary" disabled={busy || !info} onClick={() => void go()} data-testid="session-new-start">
          {busy ? "Starting..." : "New session"}
        </Button>
        {said && <span className="og-problems mono" data-testid="session-new-error">{said}</span>}
      </div>
      <p className="muted ss-new-note">
        It runs on Studio's machine with no terminal: closing this tab does not end it, End session does. Its asks wait for you in the Prompt panel.
      </p>
    </div>
  );
}

/** The Prompt header's line for a session with no terminal: the chip, Open in terminal, End session (asks first). */
export function NoTerminal({ ss }: { ss: SessionRow }) {
  const [sure, setSure] = useState(false);
  const [ending, setEnding] = useState(false);
  useEffect(() => setSure(false), [ss.session_id]);
  const copy = () => {
    const line = resumeLine(ss);
    void navigator.clipboard?.writeText(line).then(() => toast("The resume line is on the clipboard: run it in a terminal after End session", "done", 5000),
      () => toast(line, "info", 9000));
  };
  const end = async () => {
    setEnding(true);
    try {
      await api.post(`sessions/${encodeURIComponent(ss.session_id)}/command`, { cmd: "shutdown", reason: "End session (Studio)" });
      toast("Ending the session: it finishes its step, then leaves", "done");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error", 6000);
    } finally {
      setEnding(false);
      setSure(false);
    }
  };
  return (
    <span className="spp-noterm" data-testid="prompt-noterm">
      <span className="og-chip mono" title="Started from Studio: it has no terminal; this panel is its prompt">no terminal</span>
      <button className="og-link mono" onClick={copy} title={resumeLine(ss)} data-testid="prompt-open-terminal">Open in terminal</button>
      {sure ? (
        <Button size="sm" variant="danger" disabled={ending} onClick={() => void end()} data-testid="prompt-end-yes">End it</Button>
      ) : (
        <button className="og-link mono" onClick={() => setSure(true)} title="Shut this session down (it ends its current step first)" data-testid="prompt-end">End session</button>
      )}
    </span>
  );
}
