// "Agents and workflows" (3.6.0.0 R3, the design's "Adding"): a slim list in a drawer that pushes the map -- your agents
// (and this project's, then the starters), then the workflows. Every row has a grip and Add; Enter on a row adds it.
// Drag a row by its grip (or anywhere on it) onto the map: the drop places light up and say what a drop does. A row
// already on the map says so and adds nothing. Locked: nothing can be added.
import { useStore } from "../../../lib/store";
import { crew } from "../store";
import { flows } from "../flows/flowStore";
import { dragRow } from "./drag";
import { addBox, useMap } from "./mapStore";

const NONE: never[] = []; // a selector never builds a new array (a new one each read loops React)

type Item = { kind: "agent" | "workflow"; name: string; line: string; scope: string };

function uniq(rows: { name: string; does?: string; for?: string; scope: string; steps?: unknown[] }[], kind: Item["kind"]): Item[] {
  const seen = new Set<string>();
  const out: Item[] = [];
  for (const r of rows) {
    if (seen.has(r.name)) continue;
    seen.add(r.name);
    const line = kind === "workflow" ? `${(r.steps || []).length} steps · ${r.for || ""}` : r.does || "";
    out.push({ kind, name: r.name, line, scope: r.scope });
  }
  return out;
}

function Row({ it, on, locked }: { it: Item; on: boolean; locked: boolean }) {
  const add = () => { if (!on && !locked) void addBox(it.kind, it.name); };
  return (
    <div className="mp-row" data-testid="map-add-row" data-kind={it.kind} data-ref={it.name} data-on={on || undefined} tabIndex={0}
         title={`${it.kind} ${it.name}: ${it.line}${on ? " (on this map)" : locked ? " (the map is locked)" : " -- drag it onto the map, or Add"}`}
         onPointerDown={(e) => !on && dragRow(e, it.kind, it.name)}
         onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) { e.preventDefault(); add(); } }}>
      <span className="mp-grip mono" aria-hidden="true">⋮⋮</span>
      <span className="mp-row-text">
        <b>{it.name}</b>
        {it.scope !== "yours" && <span className="mp-scope"> {it.scope === "project" ? "this project's" : "starter"}</span>}
        <span className="mp-row-line">{it.line}</span>
      </span>
      <button type="button" className="btn mp-add" disabled={on || locked} onClick={add} data-testid="map-add"
              aria-label={on ? `${it.name} is on the map` : `Add ${it.name} to the map`}>{on ? "On" : "Add"}</button>
    </div>
  );
}

export function AddList() {
  const agents = useStore(crew, (s) => s.agents);
  const agentStarters = useStore(crew, (s) => s.starters);
  const flowRows = useStore(flows, (s) => s.flows);
  const flowStarters = useStore(flows, (s) => s.starters);
  const boxes = useMap((s) => s.detail?.map.boxes) || NONE;
  const locked = useMap((s) => s.locked);
  const on = new Set(boxes.flatMap((b) => (b.workflow ? [`workflow:${b.workflow}`] : (Array.isArray(b.agent) ? b.agent : [b.agent]).map((a) => `agent:${a}`))));
  const a = uniq([...agents, ...agentStarters], "agent").filter((it) => it.name !== "main"); // main is always on the map
  const w = uniq([...flowRows, ...flowStarters], "workflow");
  return (
    <div className="mp-add-list" data-testid="map-add-list">
      <p className="cw-line">Drag a row onto the map (onto a box: it hands work to it), or press Add: it waits under Not connected yet.</p>
      <div className="cw-label mono">AGENTS</div>
      {a.map((it) => <Row key={`a${it.name}`} it={it} on={on.has(`agent:${it.name}`)} locked={locked} />)}
      <div className="cw-label mono">WORKFLOWS</div>
      {w.map((it) => <Row key={`w${it.name}`} it={it} on={on.has(`workflow:${it.name}`)} locked={locked} />)}
    </div>
  );
}
