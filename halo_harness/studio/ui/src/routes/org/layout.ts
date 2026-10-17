// The Org canvas geometry (3.0.7.0 R3), the classic canvas's group-box look:
// one labelled box per position group -- the agents with no manager in the
// company are "Leadership", every other group is one manager's reports
// ("<manager>'s team", or the manager's metadata.team). A box is drawn
// around its cards wherever they are; `autoLayout` places the cards that
// have no saved position: a row of boxes per level of the chart, the cards
// in up to three columns inside their box.
import { bosses } from "./store";
import type { Agent, Pos } from "./types";

export const CARD_W = 210;
export const CARD_H = 84;
const PAD = 22;
const HEAD = 44;
const GX = 26;
const GY = 28;
const GAP = 56;
const COLS = 3;

export type Group = { key: string; label: string; manager: string; tier: number; order: number; members: Agent[] };
export type Box = { x: number; y: number; w: number; h: number };

function teamLabel(m: Agent | undefined): string {
  if (!m) return "Team";
  if (m.metadata?.team) return String(m.metadata.team);
  const chief = ["ceo", "cto", "cmo", "cfo", "pm"].includes(String(m.role)) ? String(m.role).toUpperCase() : "";
  const who = m.title && m.title.length <= 24 ? m.title : chief || m.name;
  return `${who}'s team`;
}

/** The groups, ordered by level of the chart, then by the manager's place in the list. */
export function groupsOf(agents: Agent[]): Group[] {
  const up = bosses(agents);
  const byId = new Map(agents.map((a) => [a.id, a]));
  const depth = (id: string) => {
    let d = 0;
    let cur = up.get(id);
    const seen = new Set<string>();
    while (cur && !seen.has(cur)) {
      seen.add(cur);
      d += 1;
      cur = up.get(cur);
    }
    return d;
  };
  const out = new Map<string, Group>();
  for (const a of agents) {
    const m = up.get(a.id) || "";
    const key = m ? "m:" + m : "top";
    let g = out.get(key);
    if (!g) {
      g = { key, label: m ? teamLabel(byId.get(m)) : "Leadership", manager: m, tier: m ? depth(m) + 1 : 0, order: m ? agents.findIndex((x) => x.id === m) : -1, members: [] };
      out.set(key, g);
    }
    g.members.push(a);
  }
  return [...out.values()].sort((a, b) => a.tier - b.tier || a.order - b.order || a.label.localeCompare(b.label));
}

/** Default positions for every card: rows of boxes by level, the cards in a grid inside each box. */
export function autoLayout(groups: Group[]): Record<string, Pos> {
  const pos: Record<string, Pos> = {};
  let y = 24;
  const tiers = [...new Set(groups.map((g) => g.tier))].sort((a, b) => a - b);
  for (const t of tiers) {
    let x = 24;
    let rowH = 0;
    for (const g of groups.filter((q) => q.tier === t)) {
      const cols = Math.min(COLS, g.members.length);
      const rows = Math.ceil(g.members.length / cols);
      g.members.forEach((a, i) => {
        pos[a.id] = { x: x + PAD + (i % cols) * (CARD_W + GX), y: y + HEAD + Math.floor(i / cols) * (CARD_H + GY) };
      });
      const w = PAD * 2 + cols * CARD_W + (cols - 1) * GX;
      rowH = Math.max(rowH, HEAD + rows * CARD_H + (rows - 1) * GY + PAD);
      x += w + GAP;
    }
    y += rowH + GAP;
  }
  return pos;
}

/** Every card's position: the saved one, else the default. */
export function placeAll(agents: Agent[], saved: Record<string, Pos>, groups: Group[]): Record<string, Pos> {
  const auto = autoLayout(groups);
  const out: Record<string, Pos> = {};
  for (const a of agents) out[a.id] = saved[a.id] || auto[a.id] || { x: 24, y: 24 };
  return out;
}

/** The box around a group's cards (leaving `except`, a card being dragged, out). */
export function boxOf(g: Group, pos: Record<string, Pos>, except = ""): Box | null {
  const ps = g.members.filter((a) => a.id !== except).map((a) => pos[a.id]).filter(Boolean);
  if (!ps.length) return null;
  const x = Math.min(...ps.map((p) => p.x)) - PAD;
  const y = Math.min(...ps.map((p) => p.y)) - HEAD;
  return { x, y, w: Math.max(...ps.map((p) => p.x)) + CARD_W + PAD - x, h: Math.max(...ps.map((p) => p.y)) + CARD_H + PAD - y };
}

const inside = (b: Box, p: Pos) => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;

/** What a card dropped at world point `p` lands on: another card, else the smallest box, else nothing. */
export function dropTarget(groups: Group[], pos: Record<string, Pos>, dragged: string, p: Pos): { card?: string; group?: Group } {
  for (const g of groups)
    for (const a of g.members)
      if (a.id !== dragged && pos[a.id] && inside({ x: pos[a.id].x, y: pos[a.id].y, w: CARD_W, h: CARD_H }, p)) return { card: a.id };
  let best: Group | undefined;
  let area = Infinity;
  for (const g of groups) {
    const b = boxOf(g, pos, dragged);
    if (b && inside(b, p) && b.w * b.h < area) {
      best = g;
      area = b.w * b.h;
    }
  }
  return { group: best };
}

/** The world size the canvas scrolls over. */
export function extent(pos: Record<string, Pos>): { w: number; h: number } {
  const ps = Object.values(pos);
  return { w: Math.max(600, ...ps.map((p) => p.x + CARD_W + 60)), h: Math.max(320, ...ps.map((p) => p.y + CARD_H + 60)) };
}
