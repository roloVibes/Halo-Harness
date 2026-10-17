// What the Team panels do (3.0.8.0 R2): select a member, a stage or a block
// (the Inspector follows; a block's changes load), Run a stage or the next
// one (`POST team/run`; a 422 lists its problems inline, a preflight 422
// offers "Run anyway" = force), answer a gate (`POST team/answer` accept /
// redo with text / stop), Stop the run with a reason, Validate (problems and
// preflight in a dialog), Make my first team (`POST team/init`), and open a
// stage from elsewhere (the Fleet attention queue's `o`).
import { api, ApiError } from "../../lib/api";
import { goSection, toast } from "../../lib/store";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";
import { openLineup } from "../roles/sync";
import { setView as setRolesView } from "../roles/store";
import { closeDialog, openDialog, setView, team } from "./store";
import { catchUp, loadChanges, msg, refreshAll } from "./sync";
import type { Finding, Selection, TeamDoc } from "./types";

export function select(sel: Selection): void {
  team.update((s) => (s.sel?.kind === sel?.kind && s.sel?.id === sel?.id ? {} : { sel, runProblems: null }));
  if (sel?.kind === "block") void loadChanges(sel.id);
}

/** Bring a Team panel up on its full face and focus it. */
export function showTeamPanel(id: string): void {
  goSection("team");
  setView("workspace");
  const go = () => {
    if (!layoutStore("team").get().layout) return;
    patchPanel("team", id, { collapsed: false, face: "detail" }, false);
    focusPanel("team", id);
  };
  if (layoutStore("team").get().layout) go();
  else window.setTimeout(go, 150);
}

/** The Fleet attention queue's `o` on a team_gate row: the Team section, that stage selected. */
export function openTeamStage(stage: string | undefined): void {
  if (stage) select({ kind: "stage", id: stage });
  showTeamPanel("team-inspector");
  catchUp(0);
}

/** Run `stage` (or, with null, the next pending manual stage). */
export async function runStage(stage: string | null, force = false): Promise<boolean> {
  team.update(() => ({ busy: "run", runProblems: null }));
  try {
    const body: Record<string, unknown> = stage ? { stage } : {};
    if (force) body.force = true;
    const r = await api.post<{ run: string; stage: string | null; started: boolean; queued?: boolean }>("team/run", body);
    toast(r.queued ? `${r.stage} handed to the live run` : r.stage ? `Running ${r.stage} (run ${r.run})` : `Run ${r.run}: no manual stage waits to start`, "done");
    catchUp(0);
    return true;
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) {
      const preflight = e.data.preflight === true;
      const raw = Array.isArray(e.data.problems) ? (e.data.problems as unknown[]) : [];
      const findings = preflight ? (raw as Finding[]) : [];
      const problems = preflight ? findings.filter((f) => f.severity === "blocks").map((f) => f.text + (f.fix ? ` -- fix: ${f.fix}` : "")) : raw.map(String);
      team.update(() => ({ runProblems: { stage: stage || "", problems, preflight, findings } }));
    } else toast(msg(e), "error", 5000);
    return false;
  } finally {
    team.update(() => ({ busy: "" }));
  }
}

/** Answer `stage`'s open gate: accept, redo (with the instruction) or stop. */
export async function answerGate(stage: string, action: "accept" | "redo" | "stop", text = ""): Promise<boolean> {
  team.update(() => ({ busy: "answer" }));
  try {
    const r = await api.post<{ ok: boolean; message: string }>("team/answer", { stage, action, ...(text ? { text } : {}) });
    toast(r.message || `${stage}: ${action}`, "done");
    team.update((s) => {
      const gates = { ...s.gates };
      delete gates[stage];
      return { gates };
    });
    catchUp(0);
    return true;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return false;
  } finally {
    team.update(() => ({ busy: "" }));
  }
}

export async function stopRun(reason: string): Promise<boolean> {
  team.update(() => ({ busy: "stop" }));
  try {
    const r = await api.post<{ ok: boolean; run: string }>("team/stop", { reason: reason || "stopped in Studio" });
    toast(`Run ${r.run} stops`, "done");
    closeDialog();
    catchUp(0);
    window.setTimeout(() => catchUp(0), 1200);
    return true;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return false;
  } finally {
    team.update(() => ({ busy: "" }));
  }
}

export async function validate(): Promise<void> {
  team.update(() => ({ busy: "validate" }));
  try {
    const r = await api.post<{ ok: boolean; problems: string[]; preflight: Finding[]; team: TeamDoc | null }>("team/validate", {});
    openDialog({ kind: "validate", ok: r.ok, problems: r.problems || [], preflight: r.preflight || [] });
  } catch (e) {
    toast(msg(e), "error", 5000);
  } finally {
    team.update(() => ({ busy: "" }));
  }
}

/** Make my first team: the shipped template in .halo/team.yaml, then the board. */
export async function initTeam(): Promise<void> {
  team.update(() => ({ busy: "init" }));
  try {
    const r = await api.post<{ ok: boolean; written: string[]; path: string }>("team/init", {});
    toast(`Wrote ${r.written.join(", ")}`, "done", 5000);
    setView("auto");
    await refreshAll();
  } catch (e) {
    toast(msg(e), "error", 6000);
    await refreshAll();
  } finally {
    team.update(() => ({ busy: "" }));
  }
}

/** A member's lineup: the Roles section, that lineup open on the canvas. */
export function openInRoles(lineup: string): void {
  goSection("roles");
  setRolesView("workspace");
  void openLineup(lineup);
}

export async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied", "done");
  } catch {
    toast("The browser kept the clipboard shut: select the path and copy it", "info", 5000);
  }
}
