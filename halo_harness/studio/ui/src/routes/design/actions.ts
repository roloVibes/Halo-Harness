// What the Design panels do (3.0.7.0 R3): a new project, send a turn (or the
// open comments as one), cancel the running turn, critique and contrast an
// artboard, restore a version, rename and delete an artboard, export and the
// handoff bundle, upload assets. Each says how it went in a toast or a
// dialog; the project is read again afterwards.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { closeDialog, design, live, openDialog } from "./store";
import { attach, call, loadAssets, loadProjects, openProject, reload } from "./sync";
import type { Contrast, TurnResult } from "./types";

const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));

async function run<T>(busy: string, fn: () => Promise<T>, done?: (r: T) => string): Promise<T | null> {
  design.update(() => ({ busy }));
  try {
    const r = await fn();
    if (done) toast(done(r), "done");
    return r;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return null;
  } finally {
    design.update(() => ({ busy: "" }));
  }
}

export async function newProject(name: string, model = ""): Promise<boolean> {
  if (!name.trim()) return false;
  const r = await run("new", () => api.post<{ slug: string }>("design/projects", { name: name.trim(), model }), () => `${name.trim()} created`);
  if (!r) return false;
  closeDialog();
  await loadProjects();
  await openProject(r.slug);
  design.update((s) => ({ focusSend: s.focusSend + 1 }));
  return true;
}

/** 3.1.4.0 R4: the open project's model (`PUT design/<slug>/model`; "" = the default model). */
export async function setProjectModel(model: string): Promise<boolean> {
  const r = await run("model", () => call<{ model: string }>("PUT", "model", { model }), (r) =>
    r.model ? `This project runs on ${r.model} now` : "This project runs on the default model now");
  if (!r) return false;
  await loadProjects();
  await reload();
  return true;
}

/** Run one turn with `prompt` (the message box's text by default). */
export async function send(prompt = design.get().draft, extra: Record<string, unknown> = {}, label?: string): Promise<TurnResult | null> {
  const s = design.get();
  const text = prompt.trim();
  if (!s.slug) return (toast("Make or open a project first", "info"), null);
  if (!text) return (design.update((x) => ({ focusSend: x.focusSend + 1 })), null);
  if (live(s)) return (toast("A turn already runs in this project: wait for it, or Cancel turn", "info"), null);
  const r = await run("send", () => call<{ turn: string }>("POST", "run", { prompt: text, ...extra }));
  if (!r) return null;
  if (prompt === s.draft) design.update(() => ({ draft: "" }));
  attach(r.turn, text, label);
  return null;
}

export async function cancelTurn(): Promise<void> {
  const t = design.get().turn;
  if (!t || t.done) return;
  await run("cancel", () => call("POST", `turn/${t.id}/cancel`), () => "Stopping the turn...");
}

export async function sendComments(): Promise<void> {
  const d = design.get().data;
  const open = (d?.comments || []).filter((c) => !c.resolved);
  if (!open.length) return toast("No open comments to send", "info");
  const lines = open.map((c) => `- [${c.artboard}] ${c.path ? c.path + " " : ""}at ${Math.round(c.x)}%,${Math.round(c.y)}% of the frame: ${c.text}`);
  await send("Address these comments:\n" + lines.join("\n"), {}, `${open.length} comment(s)`);
  const ids = open.map((c) => c.id);
  const tid = design.get().turn?.id;
  if (!tid) return;
  const watch = design.subscribe(() => {
    const t = design.get().turn;
    if (t && t.id === tid && !t.done) return;
    watch(); // the pins are resolved only when the turn that addressed them succeeded
    if (t && t.id === tid && t.result?.code === 0 && !t.result.cancelled) void call("POST", "comments/resolve", { ids }).then(() => reload(), () => null);
  });
}

export async function critique(aid: string): Promise<void> {
  if (live(design.get())) return toast("A turn already runs in this project", "info");
  const r = await run("critique", () => call<{ turn: string }>("POST", "critique", { artboard: aid }), () => `A second model reads ${aid} and pins its notes`);
  if (r) attach(r.turn, `Critique ${aid}`, "critique");
}

export async function contrast(aid: string): Promise<void> {
  openDialog({ kind: "contrast", aid, data: null });
  try {
    const data = await call<Contrast>("GET", `artboard/${encodeURIComponent(aid)}/contrast`);
    design.update((s) => (s.dialog?.kind === "contrast" && s.dialog.aid === aid ? { dialog: { kind: "contrast", aid, data } } : {}));
  } catch (e) {
    design.update((s) => (s.dialog?.kind === "contrast" ? { dialog: { kind: "contrast", aid, data: null, error: msg(e) } } : {}));
  }
}

export async function restore(aid: string, version: number): Promise<void> {
  const r = await run("restore", () => call("POST", `artboard/${encodeURIComponent(aid)}/restore`, { version }), () => `${aid}: v${version} is the newest version again`);
  if (r) {
    design.update((s) => {
      const view = { ...s.view };
      delete view[aid];
      return { view, bust: { ...s.bust, [aid]: (s.bust[aid] || 0) + 1 } };
    });
    await reload();
  }
}

export async function rename(aid: string, name: string): Promise<void> {
  const r = await run("rename", () => call("POST", `artboard/${encodeURIComponent(aid)}/rename`, { name }), () => `Renamed to ${name}`);
  if (r) (closeDialog(), await reload());
}

export async function remove(aid: string): Promise<void> {
  const r = await run("delete", () => api.del(`design/${encodeURIComponent(design.get().slug)}/artboard/${encodeURIComponent(aid)}`), () => `${aid} deleted`);
  if (r) (closeDialog(), await reload());
}

export async function exportAs(as: string, artboard = ""): Promise<void> {
  const r = await run("export", () => call<{ lines: string[] }>("POST", "export", { as, artboard }));
  if (r) openDialog({ kind: "exported", as, lines: r.lines || [] });
}

export async function handoff(): Promise<void> {
  const r = await run("handoff", () => call<{ path: string }>("POST", "handoff", {}));
  if (r) openDialog({ kind: "handoff", path: r.path });
}

const base64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => reject(new Error("could not read " + file.name));
    r.readAsDataURL(file);
  });

/** Upload files into assets/; each one's path goes into the message box. */
export async function upload(files: File[]): Promise<void> {
  if (!design.get().slug) return toast("Open a project first", "info");
  for (const f of files) {
    const row = await run("upload", async () => call<{ path: string }>("POST", "assets", { name: f.name, data_base64: await base64(f) }), (r) => `${r.path} uploaded`);
    if (row) addToDraft(`Use ${row.path} `);
  }
  await loadAssets();
}

export function addToDraft(text: string): void {
  design.update((s) => ({ draft: (s.draft ? s.draft.replace(/\s+$/, "") + "\n" : "") + text, focusSend: s.focusSend + 1 }));
}
