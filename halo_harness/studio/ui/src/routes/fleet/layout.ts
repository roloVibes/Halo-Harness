// The fleet map laid out in code (no layout library): one labelled group box
// per harness (this harness first), or per repo with "By project"; inside, a
// card per session and its agents under it as a tree (each child indented
// under its parent, an elbow edge from the parent). Boxes flow in rows of at
// most MAX_COLS. Pure: Map.tsx draws what this returns. By project, a card
// is taller: its third line holds the git chips (dirty / ahead / behind,
// the worktree) from GET fleet/conflicts' rooms.
import { keyOf, treeOf } from "./store";
import type { AgentKey, AgentRef, Harness, SessionRow } from "./types";

const BOX_W = 340;
const PAD = 14;
const HEAD = 44;
const CARD_H = 52;
const CARD_H_ROOM = 68;
const NODE_H = 40;
const GAP = 6;
const INDENT = 18;
const S_GAP = 14;
const BOX_GAP = 26;
const MAX_COLS = 3;
const MARGIN = 6;

export type Rect = { x: number; y: number; w: number; h: number };
export type Box = Rect & { key: string; label: string; sub: string; online: boolean; local: boolean; hc: string; empty: boolean };
export type Card = Rect & { harness: Harness; session: SessionRow; hc: string };
export type NodeBox = Rect & { ref: AgentRef; hc: string };
export type Edge = { from: AgentKey | null; to: AgentKey; d: string };
export type Geometry = { width: number; height: number; boxes: Box[]; cards: Card[]; nodes: NodeBox[]; edges: Edge[] };

type Group = { key: string; label: string; sub: string; online: boolean; local: boolean; hc: string; rows: { h: Harness; s: SessionRow }[] };

const hcOf = (all: Harness[], id: string) => String(Math.max(0, all.findIndex((h) => h.id === id)) % 10);

function projectKey(s: SessionRow): string {
  const p = s.project || {};
  return String(p.repo || p.root || s.cwd || "no project");
}

export function projectLabel(s: SessionRow): string {
  const p = s.project || {};
  const name = String(p.repo || p.root || s.cwd || "").replace(/[\\/]+$/, "").split(/[\\/]/).pop() || "no project";
  return p.branch ? `${name} · ${p.branch}${p.dirty ? "*" : ""}` : name;
}

function groups(harnesses: Harness[], byProject: boolean): Group[] {
  if (!byProject)
    return harnesses.map((h) => ({
      key: "h:" + h.id,
      label: h.name || h.id.slice(0, 8),
      sub: [h.local ? "this harness" : h.online ? "online" : "offline", h.local ? "" : h.host, h.version].filter(Boolean).join(" · "),
      online: h.local || !!h.online,
      local: !!h.local,
      hc: hcOf(harnesses, h.id),
      rows: (h.sessions || []).map((s) => ({ h, s })),
    }));
  const out = new Map<string, Group>();
  for (const h of harnesses)
    for (const s of h.sessions || []) {
      const k = projectKey(s);
      if (!out.has(k)) out.set(k, { key: "p:" + k, label: projectLabel(s).split(" · ")[0], sub: "", online: true, local: false, hc: "", rows: [] });
      out.get(k)!.rows.push({ h, s });
    }
  for (const g of out.values()) {
    const who = new Set(g.rows.map((r) => r.h.name || r.h.id.slice(0, 8)));
    g.sub = `${who.size} harness${who.size === 1 ? "" : "es"} · ${g.rows.length} session${g.rows.length === 1 ? "" : "s"}`;
  }
  return [...out.values()];
}

function place(g: Group, harnesses: Harness[], ox: number, oy: number, geo: Geometry, cardH: number): number {
  let y = HEAD;
  const inner = BOX_W - 2 * PAD;
  for (const { h, s } of g.rows) {
    const hc = hcOf(harnesses, h.id);
    const card: Card = { x: ox + PAD, y: oy + y, w: inner, h: cardH, harness: h, session: s, hc };
    geo.cards.push(card);
    y += cardH + GAP;
    const pos = new Map<string, NodeBox>();
    for (const { a, depth } of treeOf(s.agents || [])) {
      const key = keyOf(h.id, s.session_id, a.agent_id);
      const x = ox + PAD + 12 + depth * INDENT;
      const n: NodeBox = { x, y: oy + y, w: inner - 12 - depth * INDENT, h: NODE_H, ref: { key, h, s, a, depth }, hc };
      geo.nodes.push(n);
      pos.set(a.agent_id, n);
      const parent = a.parent ? pos.get(a.parent) : undefined;
      const x0 = parent ? parent.x + 9 : card.x + 9;
      const y0 = parent ? parent.y + NODE_H : card.y + cardH;
      geo.edges.push({ from: parent ? parent.ref.key : null, to: key, d: `M${x0} ${y0} V${n.y + NODE_H / 2} H${n.x}` });
      y += NODE_H + GAP;
    }
    y += S_GAP - GAP;
  }
  if (!g.rows.length) y += 34;
  return y + PAD - S_GAP + GAP;
}

export function layout(harnesses: Harness[], byProject: boolean): Geometry {
  const geo: Geometry = { width: 0, height: 0, boxes: [], cards: [], nodes: [], edges: [] };
  const gs = groups(harnesses, byProject);
  const cols = Math.max(1, Math.min(MAX_COLS, gs.length));
  let rowY = MARGIN;
  for (let i = 0; i < gs.length; i += cols) {
    let rowH = 0;
    gs.slice(i, i + cols).forEach((g, j) => {
      const x = MARGIN + j * (BOX_W + BOX_GAP);
      const h = place(g, harnesses, x, rowY, geo, byProject ? CARD_H_ROOM : CARD_H);
      geo.boxes.push({ x, y: rowY, w: BOX_W, h, key: g.key, label: g.label, sub: g.sub, online: g.online, local: g.local, hc: g.hc, empty: !g.rows.length });
      rowH = Math.max(rowH, h);
    });
    rowY += rowH + BOX_GAP;
  }
  geo.width = MARGIN * 2 + cols * BOX_W + (cols - 1) * BOX_GAP;
  geo.height = Math.max(120, rowY - BOX_GAP + MARGIN);
  return geo;
}
