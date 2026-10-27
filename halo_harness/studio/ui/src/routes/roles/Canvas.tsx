// roles-graph (3.0.7.0 R2; the drawn canvas inside it is data-testid roles-canvas):
// the open lineup as cards in tier boxes (layout.ts), the delegation
// and pipeline edges between them. Drag a card to move it (saved
// 500 ms after the last move); drop it into another tier box and the
// lineup's tiers change and save (the main agent stays in tier 0: the card
// snaps back with the rule). A tier's label strip collapses it. Drag a bio from the Bios panel
// onto the canvas to add it. Click the canvas, then A lays out, F fits, + and
// - zoom, the arrows nudge the selected card, Delete removes it (asks first).
// 3.1.5.0 R3: the glow's life and its legend (glow.ts, GlowLegend.tsx), a
// tier box in its cards' state colour, and an empty canvas that invites
// ("Drag a bio here, or New lineup", CanvasEmpty.tsx). 3.1.6.0 R1: Add tier
// on the bar, a tier box's own head and menu (TierBox.tsx, TierMenu.tsx);
// when the tiers change (one added or deleted) and the boxes then overlap,
// the canvas lays itself out again in tier columns. 3.2.2.0 R5 (drop.ts): a
// drop makes room -- the dropped card keeps its spot, the cards it lands on
// step aside in their tier (live while it moves), a drop into another tier
// lands beside the card it hits; a collapsed tier is no drop target (held
// over its strip for 600 ms it opens; dropped there, the card stays where it
// was); the selected or last-dropped card is drawn on top; the world grows
// with the drag. 3.3.0.0 R7 (a slow box): a drop into another tier is one
// ordered write (actions.ts `moveToTier`), and a tier a hold opened is the
// drop's target, its box as the store has it at the release.
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type KeyboardEvent, type PointerEvent } from "react";
import { addCard, moveToTier } from "./actions";
import { Card, Edges } from "./CanvasParts";
import { TierBox } from "./TierBox";
import { TierMenu } from "./TierMenu";
import { focusModel } from "./modelActions";
import { CanvasBar } from "./CanvasBar";
import { CanvasInvite, NoLineup } from "./CanvasEmpty";
import { dropPatch } from "./drop";
import { toast } from "../../lib/store";
import { GlowLegend } from "./GlowLegend";
import { glowOf, hideLegend, startGlow, type GlowState } from "./glow";
import { autoLayout, columns, extent, hiddenCards, placeAll, tierAt, tierBox } from "./layout";
import { cardActivity, selectCard, useByNode } from "./live";
import { ReplayBar } from "./Replay";
import { openDialog, roles, useRoles } from "./store";
import { movePositions, setCollapsed } from "./sync";
import type { Pos } from "./types";

type Drag = { id: string; dx: number; dy: number; hot: string };
const OPEN_MS = 600; // a card held this long over a collapsed tier's strip opens it

export function CanvasDetail() {
  const graph = useRoles((s) => s.graph);
  const saved = useRoles((s) => s.positions);
  const collapsed = useRoles((s) => s.collapsed);
  const sel = useRoles((s) => s.sel);
  const models = useRoles((s) => s.models);
  const gym = useRoles((s) => s.gym);
  const findings = useRoles((s) => s.findings);
  const name = useRoles((s) => s.name);
  const loaded = useRoles((s) => s.loaded);
  const replaying = useRoles((s) => !!s.replay);
  const byNode = useByNode();
  useEffect(() => startGlow(), []);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [zoom, setZoom] = useState(1);
  const [top, setTop] = useState(""); // the last-dropped card, drawn over the others
  const scroll = useRef<HTMLDivElement>(null);
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const placed = useMemo(() => (graph ? placeAll(graph, saved) : {}), [graph, saved]);
  const pos = useMemo(() => {
    if (!graph || !drag || !placed[drag.id]) return placed;
    const at = { x: Math.max(0, placed[drag.id].x + drag.dx), y: Math.max(0, placed[drag.id].y + drag.dy) };
    const into = graph.tiers.find((t) => t.name === drag.hot);
    return { ...placed, ...dropPatch(graph, placed, collapsed, drag.id, at, into), [drag.id]: at }; // the room being made, live
  }, [graph, placed, collapsed, drag]);
  const xs = useMemo(() => (graph ? columns(graph) : []), [graph]);
  const hidden = useMemo(() => (graph ? hiddenCards(graph, collapsed) : new Set<string>()), [graph, collapsed]);
  const issues = useMemo(() => {
    const out: Record<string, number> = {};
    for (const f of findings) if (f.node) out[f.node] = (out[f.node] || 0) + 1;
    return out;
  }, [findings]);
  const lit = useMemo(() => new Set(Object.keys(byNode).filter((id) => byNode[id].some((a) => a.state === "running"))), [byNode]);
  const glows = useMemo(() => Object.fromEntries(Object.keys(byNode).map((id) => [id, glowOf(cardActivity(byNode[id]))])) as Record<string, GlowState | "">, [byNode]);
  const tierGlow = (ids: string[]): GlowState | "" => (["failed", "waiting", "working", "done"] as GlowState[]).find((g) => ids.some((id) => glows[id] === g)) || "";

  const world = (ev: { clientX: number; clientY: number }): Pos => {
    const r = scroll.current!.getBoundingClientRect();
    return { x: (ev.clientX - r.left + scroll.current!.scrollLeft) / zoomRef.current, y: (ev.clientY - r.top + scroll.current!.scrollTop) / zoomRef.current };
  };

  const onCard = useCallback((ev: PointerEvent<HTMLElement>, id: string) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    scroll.current?.focus({ preventScroll: true });
    const x0 = ev.clientX, y0 = ev.clientY;
    let moved = false;
    let last: Drag = { id, dx: 0, dy: 0, hot: "" };
    let held = "", timer = 0; // the collapsed strip under the pointer, and its open timer
    let opened = ""; // 3.3.0.0 R7: the tier this hold opened (the drop's target while the pointer stays over it)
    const hold = (name: string) => {
      if (name === held) return;
      window.clearTimeout(timer);
      held = name;
      if (name) timer = window.setTimeout(() => ((opened = name), setCollapsed(name, false)), OPEN_MS);
    };
    const move = (m: globalThis.PointerEvent) => {
      const dx = (m.clientX - x0) / zoomRef.current, dy = (m.clientY - y0) / zoomRef.current;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      const s = roles.get();
      // the boxes from the store as it is at this move (never the drawn ones: the room a drag makes moves the
      // target tier's cards away from the pointer)
      const all = placeAll(s.graph!, s.positions);
      hold(tierAt(s.graph!, all, s.collapsed, world(m), id, true)?.name || "");
      const hot = tierAt(s.graph!, all, s.collapsed, world(m), id)?.name || "";
      if (opened && hot !== opened) opened = ""; // left the tier it opened
      last = { id, dx, dy, hot };
      setDrag(last);
    };
    const up = (u: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.clearTimeout(timer);
      setDrag(null);
      if (!moved) return selectCard(id);
      const s = roles.get();
      if (!s.graph) return;
      const all = placeAll(s.graph, s.positions);
      const p = world(u);
      setTop(id);
      const shut = tierAt(s.graph, all, s.collapsed, p, id, true);
      if (shut) return toast(`tier ${shut.name} is collapsed; it stays where it was`, "info", 3500);
      const from = s.graph.tiers.find((t) => t.node_ids.includes(id));
      // 3.3.0.0 R7: a tier the hold opened is the target while the pointer stays over it; the drop point is clamped
      // into its box as the store has it NOW (dropPatch over `all`, read at release), never a box from before the hold
      const to = (opened && !s.collapsed[opened] && s.graph.tiers.find((t) => t.name === opened)) || tierAt(s.graph, all, s.collapsed, p, id);
      const next = { x: Math.max(0, all[id].x + last.dx), y: Math.max(0, all[id].y + last.dy) };
      if (to && from && to.name !== from.name) {
        void moveToTier(id, to.name, dropPatch(s.graph, all, s.collapsed, id, next, to)); // one ordered write (actions.ts)
        return;
      }
      movePositions(dropPatch(s.graph, all, s.collapsed, id, next));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const ext = graph ? extent(graph, pos) : { w: 600, h: 320 }; // grows with a live drag
  const fit = () => {
    const el = scroll.current;
    if (el) setZoom(Math.max(0.3, Math.min(1.25, (el.clientWidth - 24) / ext.w, (el.clientHeight - 24) / ext.h)));
  };
  const layout = () => graph && movePositions(autoLayout(graph));
  const fitted = useRef("");
  const shape = useRef("");
  const tierShape = graph ? graph.tiers.map((t) => `${t.index}:${t.implicit ? "~" : ""}`).join(",") : "";
  useEffect(() => {
    // the first time a lineup draws, and when its tiers change: boxes that overlap (a layout saved before the
    // tier boxes, or a tier just added or deleted) are laid out again; the first draw then fits it
    const el = scroll.current;
    if (!el || !graph || !name || (fitted.current === name && shape.current === tierShape)) return;
    const first = fitted.current !== name;
    fitted.current = name;
    shape.current = tierShape;
    const xs = columns(graph);
    const boxes = graph.tiers.map((t, i) => tierBox(t, xs[i], placed, !!collapsed[t.name]));
    const overlap = boxes.some((a, i) => boxes.some((b, j) => j > i && a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h));
    if (overlap) movePositions(autoLayout(graph));
    if (first && (ext.w > el.clientWidth || ext.h > el.clientHeight)) setZoom(Math.max(0.3, Math.min(1, (el.clientWidth - 24) / ext.w, (el.clientHeight - 24) / ext.h)));
  }, [name, graph, placed, collapsed, ext.w, ext.h, tierShape]);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    const step = e.shiftKey ? 40 : 8;
    const arrows: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (arrows[k] && sel && placed[sel]) {
      const [dx, dy] = arrows[k];
      movePositions({ [sel]: { x: Math.max(0, placed[sel].x + dx), y: Math.max(0, placed[sel].y + dy) } });
    } else if ((k === "Delete" || k === "Backspace") && sel) openDialog({ kind: "delete-card", node: sel });
    else if (k === "Enter" && sel) focusModel(sel); // 3.1.4.0 R4: the Inspector's MODEL strip
    else if (k === "a") layout();
    else if (k === "f" && !e.shiftKey) fit(); // 3.3.2.0 R1: Shift+F is Focus
    else if (k === "+" || k === "=") setZoom((z) => Math.min(2, z * 1.2));
    else if (k === "-") setZoom((z) => Math.max(0.3, z / 1.2));
    else return;
    e.preventDefault();
  };
  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (e.dataTransfer.types.includes("text/halo-bio")) (e.preventDefault(), (e.dataTransfer.dropEffect = "copy"));
  };
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    const bio = e.dataTransfer.getData("text/halo-bio");
    if (!bio) return;
    e.preventDefault();
    const kind = roles.get().bios.find((b) => b.name === bio)?.kind || "subagent";
    addCard(bio, ["main", "subagent", "reviewer", "researcher", "judge"].includes(kind) ? kind : "subagent");
  };

  if (!loaded) return null; // 3.3.2.0 R3: the section's own wait says it while it reads (RolesView)
  if (!graph || !name) return <NoLineup />;
  return (
    <div className="rc" data-testid="roles-canvas" data-lineup={name} data-replaying={replaying || undefined}>
      <CanvasBar zoom={zoom} setZoom={setZoom} fit={fit} layout={layout} />
      <div className="rc-scroll" ref={scroll} tabIndex={0} onKeyDown={onKey} onDragOver={onDragOver} onDrop={onDrop} onScroll={hideLegend}
           onPointerDown={(e) => e.target === e.currentTarget && roles.update(() => ({ sel: "" }))} aria-label="Roles canvas: the lineup's cards in their tier boxes">
        <div className="rc-world" style={{ width: ext.w * zoom, height: ext.h * zoom }}>
          <div className="rc-inner" style={{ width: ext.w, height: ext.h, transform: `scale(${zoom})` }}>
            {graph.tiers.map((t, i) => (
              <TierBox key={t.name} t={t} b={tierBox(t, xs[i], pos, !!collapsed[t.name])} count={t.node_ids.length} state={tierGlow(t.node_ids)}
                       collapsed={!!collapsed[t.name]} hot={drag?.hot === t.name} onToggle={(n) => setCollapsed(n, !roles.get().collapsed[n])} />
            ))}
            <Edges edges={graph.edges} pos={pos} hidden={hidden} w={ext.w} h={ext.h} sel={sel} lit={lit} glows={glows} />
            {graph.nodes.filter((n) => !hidden.has(n.id)).map((n) => {
              const list = byNode[n.id] || [];
              return (
                <Card key={n.id} n={n} x={pos[n.id]?.x ?? 0} y={pos[n.id]?.y ?? 0} model={models.find((m) => m.ref === n.model)} gym={gym[n.model]}
                      issues={issues[n.id] || 0} selected={n.id === sel} top={n.id === top} dragging={drag?.id === n.id} live={list} activity={cardActivity(list)} onDown={onCard} />
              );
            })}
          </div>
          {!graph.nodes.length && <CanvasInvite />}
        </div>
      </div>
      <ReplayBar />
      <GlowLegend />
      <TierMenu />
    </div>
  );
}
