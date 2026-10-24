// A pack's panels as workspace PanelSpecs (3.2.0.0 R3). Each spec's faces
// read their panel from the registry by id, so a reload (a grant, an update)
// redraws them in place; the components are made once per panel id. The
// title bar's source line is "from pack <id>"; `?` and the ... menu's Help
// show the pack's own `help` lines (every panel has them: the owner's clarity
// rule). In a pack's section the panels fill the 24 columns left to right,
// a row at a time; in a core section they go under the section's own panels,
// as strips.
import type { ComponentType } from "react";
import { Empty } from "../../lib/ui";
import type { PanelSpec } from "../../lib/workspace/types";
import { PackForm } from "./PackForm";
import { PackBundle, PackEvents } from "./PackEvents";
import { PackLinks, PackMarkdown, PackTable } from "./kinds";
import { findPanel, usePacks } from "./store";
import type { PackPanel } from "./types";

const COLS = 24;
const CORE_Y = 400; // under every core panel: the grid packs them up
const KIND_LINE: Record<string, string> = {
  markdown: "a page of the pack", table: "rows the pack keeps", form: "the pack's settings", links: "where to go next",
  events: "the pack's live lines", bundle: "the pack's own script",
};

function Body({ id }: { id: string }) {
  const p = usePacks((s) => findPanel(id, s.reg));
  if (!p) return <Empty title="This panel's pack is off" body="Enable the pack again (halo pack enable) and it comes back." />;
  switch (p.kind) {
    case "markdown":
      return <PackMarkdown p={p} />;
    case "table":
      return <PackTable p={p} />;
    case "form":
      return <PackForm p={p} />;
    case "links":
      return <PackLinks p={p} />;
    case "events":
      return <PackEvents p={p} />;
    case "bundle":
      return <PackBundle p={p} />;
    default:
      return <Empty title="Studio does not draw this kind" body={String((p as PackPanel).kind)} />;
  }
}

function Glance({ id }: { id: string }) {
  const p = usePacks((s) => findPanel(id, s.reg));
  return (
    <div className="glance" data-testid="pack-glance">
      <div className="glance-kicker mono">PACK {p?.pack.toUpperCase()}</div>
      <div className="glance-hint">{p ? p.help.split("\n")[0] || KIND_LINE[p.kind] : ""}</div>
    </div>
  );
}

const faces = new Map<string, { glance: ComponentType; detail: ComponentType }>();

function facesOf(id: string) {
  let f = faces.get(id);
  if (!f) {
    f = { glance: () => <Glance id={id} />, detail: () => <Body id={id} /> };
    faces.set(id, f);
  }
  return f;
}

function spec(p: PackPanel, x: number, y: number): PanelSpec {
  const w = Math.max(4, Math.min(COLS, p.w || 12));
  const help = p.help || `${p.title}: ${KIND_LINE[p.kind] || p.kind}, from pack ${p.pack}.`;
  return { id: p.id, testid: "pack-panel", title: p.title, x, y, w, h: Math.max(8, p.h || 24), minW: 4, minH: 8, face: "detail",
           collapsed: p.collapsed, about: p.about, help, ...facesOf(p.id) };
}

/** A pack section's panels, left to right, a row at a time. */
export function sectionSpecs(list: PackPanel[]): PanelSpec[] {
  let x = 0;
  let y = 0;
  let rowH = 0;
  return list.map((p) => {
    const w = Math.max(4, Math.min(COLS, p.w || 12));
    if (x + w > COLS) {
      y += rowH;
      x = 0;
      rowH = 0;
    }
    const out = spec(p, x, y);
    x += w;
    rowH = Math.max(rowH, out.h);
    return out;
  });
}

/** Panels a pack adds to a core section: strips under the section's own. */
export function coreSpecs(list: PackPanel[]): PanelSpec[] {
  return list.map((p, i) => spec(p, 0, CORE_Y + i * 6));
}
