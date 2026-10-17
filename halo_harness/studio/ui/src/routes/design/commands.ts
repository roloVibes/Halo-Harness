// The palette's Design group (3.0.7.0 R3): new project, send (the message
// box's text; with an empty box it moves the focus there), cancel turn,
// export, handoff, send comments, and open any project by name.
import { goSection } from "../../lib/store";
import { cancelTurn, handoff, send, sendComments } from "./actions";
import { design, live, openDialog } from "./store";
import { openProject, startDesign } from "./sync";

export type DesignCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

function inDesign(fn: () => void): () => void {
  return () => {
    goSection("design");
    startDesign();
    window.setTimeout(fn, 60);
  };
}

export function designCommands(): DesignCommand[] {
  const s = design.get();
  const g = "Design";
  const name = s.data?.meta.name || "the project";
  const out: DesignCommand[] = [
    { id: "design-new", group: g, label: "Design: new project", hint: "a name and, if you like, its model", run: inDesign(() => openDialog({ kind: "new" })) },
    { id: "design-send", group: g, label: "Design: send", hint: s.draft.trim() ? `run a turn in ${name}: "${s.draft.trim().slice(0, 40)}"` : "the message box: say what to make or change", run: inDesign(() => void send()) },
  ];
  if (live(s)) out.push({ id: "design-cancel", group: g, label: "Design: cancel turn", hint: `stop the turn running in ${name}`, run: () => void cancelTurn() });
  if (s.data) {
    out.push(
      { id: "design-export", group: g, label: "Design: export", hint: "a folder, HTML, PNG, SVG or PDF", run: inDesign(() => openDialog({ kind: "export" })) },
      { id: "design-handoff", group: g, label: "Design: handoff bundle", hint: "the artboards, the system and HANDOFF.md for the next session", run: inDesign(() => void handoff()) },
    );
    const pins = s.data.comments.filter((c) => !c.resolved).length;
    if (pins) out.push({ id: "design-comments", group: g, label: `Design: send comments (${pins})`, hint: "the open pins as one turn", run: inDesign(() => void sendComments()) });
  }
  for (const p of (s.projects || []).slice(0, 30))
    if (p.slug !== s.slug) out.push({ id: "design-open-" + p.slug, group: g, label: `Design: open ${p.name}`, hint: `${p.artboards} artboard(s)`, run: inDesign(() => void openProject(p.slug)) });
  return out;
}
