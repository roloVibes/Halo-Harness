// Agents -> Workflows (3.3.16.0 R3, docs/STUDIO-agents.md "Workflows"): the board of squares main may hand work to. The
// rules it is built by (ROADMAP "Clean and clear"): nothing opens on load; the empty board is one sentence and a Library
// button; one fixed-size square per enabled workflow on the 12 px grid, never overlapping (Edges.tsx `layout`); main's
// lines to them still at rest, a moving dash only toward the square at work, one glowing square at a time; a drop
// raises one confirm card (what / cost / time / writes) and is the only way on, the card's `x` the only way off, both
// saying what changed in one line. Keys: arrows move the selection, Enter opens the inspector, Delete asks in the
// inspector, `/` focuses the library's search, Esc clears.
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { studio } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { startFleet } from "../../fleet/sync";
import { useFleet } from "../../fleet/store";
import { agents } from "../store";
import { Card } from "./Card";
import { Edges, layout, MAIN_H, MAIN_W, PAD } from "./Edges";
import { DRAG_TYPE, Library, LibraryButton } from "./Library";
import {
  cancelConfirm, dropped, enableSquare, loadBoard, onBoard, openLibrary, select, squareOf, useWf, wf, workingSquare, writesLine,
} from "./store";
import { WorkflowSummary } from "./WorkflowSummary";
import { BlockConfirm, BlockNote } from "../blocks/BlockOverlay"; // 3.3.16.3: a template dropped here
import { useAgentsView } from "../store";

const TYPING = "input, textarea, select, [contenteditable]";

function Confirm() {
  const ref = useWf((s) => s.confirm);
  const q = useWf((s) => squareOf(s, s.confirm));
  const board = useWf((s) => s.board);
  const busy = useWf((s) => s.busy);
  if (!ref || !q) return null;
  return (
    <div className="wf-confirm" role="group" aria-label={`Enable ${q.ref}`} data-testid="wf-confirm" data-ref={q.ref}>
      <b className="wf-confirm-title">Enable {q.ref} for {board?.where || "this lineup"}?</b>
      <dl className="wf-confirm-lines">
        <div><dt className="mono">WHAT</dt><dd>main may hand {q.ref} work: {q.does}</dd></div>
        <div><dt className="mono">COST</dt><dd>nothing now; each hand-off: {q.costs}</dd></div>
        <div><dt className="mono">TIME</dt><dd>at once; each hand-off: {q.limits}</dd></div>
        <div><dt className="mono">WRITES</dt><dd>{writesLine(board).replace(/^writes: /, "")}</dd></div>
      </dl>
      <div className="wf-page-actions" data-density="bar">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => void enableSquare(q.ref)} data-testid="wf-confirm-enable">Enable</Button>
        <Button size="sm" variant="ghost" onClick={cancelConfirm} data-testid="wf-confirm-cancel">Cancel</Button>
      </div>
    </div>
  );
}

function useBoardKeys(refs: string[], cols: number): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = studio.get();
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || st.section !== "agents" || !agents.get().board) return;
      if (st.paletteOpen || st.help || document.querySelector("[role=dialog]")) return;
      if ((e.target as HTMLElement | null)?.closest?.(TYPING)) return;
      const s = wf.get();
      const at = Math.max(0, refs.indexOf(s.focus || s.selected));
      const move: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols };
      if (e.key === "/") return e.preventDefault(), openLibrary(true);
      if (e.key === "Escape") return wf.update(() => ({ selected: "", hover: "", page: "summary", confirm: "" }));
      if (!refs.length) return;
      if (e.key in move) {
        e.preventDefault();
        const next = refs[Math.min(refs.length - 1, Math.max(0, (s.focus || s.selected ? at + move[e.key] : 0)))];
        wf.update((x) => ({ focus: next, ...(x.selected ? { selected: next, page: "summary" as const } : {}) }));
      } else if (e.key === "Enter" && (s.focus || s.selected)) {
        e.preventDefault();
        select(s.focus || s.selected);
      } else if ((e.key === "Delete" || e.key === "Backspace") && (s.focus || s.selected)) {
        e.preventDefault();
        select(s.focus || s.selected, "remove");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [refs, cols]);
}

export function Board() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const board = useWf((s) => s.board);
  const squares = useMemo(() => onBoard({ ...wf.get(), board }), [board]);
  const loaded = useWf((s) => !!s.board);
  const error = useWf((s) => s.error);
  const note = useWf((s) => s.note);
  const selected = useWf((s) => s.selected);
  const focus = useWf((s) => s.focus);
  const inspecting = useWf((s) => !!(s.selected || s.hover));
  const library = useWf((s) => s.library);
  const shown = useAgentsView() === "workflows"; // the library and the block cards draw once: on the view that shows
  const workingKey = useFleet(workingSquare);
  const working = workingKey ? { name: workingKey.split("|")[0], cost: Number(workingKey.split("|")[1]) || 0 } : null;
  useEffect(() => {
    void loadBoard();
    startFleet();
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const refs = squares.map((q) => q.ref);
  const { boxes, height, cols } = layout(refs, width);
  useBoardKeys(refs, cols);
  const live = working && refs.includes(working.name) ? working.name : "";
  const over = (e: DragEvent) => e.dataTransfer.types.includes(DRAG_TYPE) && (e.preventDefault(), (e.dataTransfer.dropEffect = "copy"));
  const drop = (e: DragEvent) => {
    const got = e.dataTransfer.getData(DRAG_TYPE);
    if (got) e.preventDefault(), dropped(got);
  };
  const clear = (e: { target: unknown; currentTarget: unknown }) => e.target === e.currentTarget && wf.update(() => ({ selected: "", hover: "" }));
  return (
    <div className="wf" data-testid="wf-board-view" data-library={library || undefined} data-inspecting={inspecting || undefined}>
      {shown && <Library />}
      <div className="wf-board" ref={ref} data-testid="wf-board" data-count={refs.length} data-working={live || undefined}
           onDragOver={over} onDrop={drop} onClick={clear}>
        {note && <div className="wf-note mono" data-testid="wf-note" role="status">{note}
          <button className="icon-btn" onClick={() => wf.update(() => ({ note: "" }))} aria-label="Dismiss this line">×</button></div>}
        {error && <p className="wf-err" data-testid="wf-error">{error}</p>}
        {loaded && !refs.length ? (
          <div className="wf-empty" data-testid="wf-empty">
            <p>No workflows enabled: drag one from the library, or <span className="mono">halo workflows enable media</span></p>
            <LibraryButton />
          </div>
        ) : (
          <div className="wf-world" style={{ height }} onClick={clear}>
            <Edges boxes={boxes} working={live} width={Math.max(width, 2 * PAD + MAIN_W)} height={height} />
            <div className="wf-main" style={{ left: PAD, top: PAD, width: MAIN_W, height: MAIN_H }} data-testid="wf-main">
              <b className="mono">main</b><span className="muted">hands work to {refs.length} square{refs.length === 1 ? "" : "s"}</span>
              {working && <span className="mono wf-main-cost" data-testid="wf-working-cost">{working.name} ${working.cost.toFixed(4)}</span>}
            </div>
            {boxes.map((b) => {
              const q = squares.find((x) => x.ref === b.ref);
              return q ? <Card key={b.ref} sq={q} box={b} working={b.ref === live} selected={selected === b.ref} focused={focus === b.ref} /> : null;
            })}
          </div>
        )}
        <Confirm />
        {shown && <BlockNote />}
        {shown && <BlockConfirm />}
      </div>
      <WorkflowSummary />
    </div>
  );
}
