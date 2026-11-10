// The keyboard's drag (3.3.16.3, docs/STUDIO-blocks.md "Keys"): with a card or a square's agent focused, M starts a move;
// the arrows pick the block it goes into (every square block and every tier but its own, lit as the pointer's target
// is); Enter makes the move -- into a square it raises the confirm card, into a tier a card moves as the drag moves it
// (one ordered save) and an agent joins it; Esc stops. On a focused agent, Delete asks in the inspector (its block's
// Agents page); on a focused block, Delete asks there too (Take it off).
import { useEffect } from "react";
import { createStore, studio, useStore } from "../../../lib/store";
import { moveToTier } from "../../roles/actions";
import { roles } from "../../roles/store";
import { onBoard, select, wf } from "../workflows/store";
import { targetKey, useDrag } from "./drag";
import { offerIntoTier } from "./ops";
import { offerJoin } from "./opsSquare";
import { askOut, selectBlock } from "./blockState";

type Tgt = { kind: "square" | "tier"; name: string; label: string };
type Moving = { bio: string; from: string; card: string; targets: Tgt[]; at: number } | null;

export const moving = createStore<{ m: Moving }>({ m: null });
export const useMoving = (): Moving => useStore(moving, (s) => s.m);
/** The block a drag or a keyboard move would land in now ("square:<ref>" | "tier:<name>" | ""). */
export function useHotTarget(): string {
  const drag = useDrag((s) => targetKey(s.target));
  const key = useStore(moving, (s) => (s.m ? `${s.m.targets[s.m.at]?.kind}:${s.m.targets[s.m.at]?.name}` : ""));
  return key || drag;
}

function targetsFor(from: string, card: string): Tgt[] {
  const g = roles.get().graph;
  const own = card ? g?.tiers.find((t) => t.node_ids.includes(card))?.name : "";
  const sq = onBoard(wf.get()).filter((q) => q.ref !== from).map((q) => ({ kind: "square" as const, name: q.ref, label: `${q.ref} (square)` }));
  const tiers = (g?.tiers || []).filter((t) => !t.implicit && t.name !== own && t.index > 0).map((t) => ({ kind: "tier" as const, name: t.name, label: `tier ${t.name}` }));
  return [...sq, ...tiers];
}

function start(el: HTMLElement): boolean {
  const agent = el.closest<HTMLElement>('[data-testid="block-agent"]');
  const card = el.closest<HTMLElement>('[data-testid="roles-card"]');
  const bio = agent?.dataset.bio || card?.dataset.agent || "";
  if (!bio || (card && card.dataset.role === "main")) return false;
  const from = agent?.dataset.from || "";
  const targets = targetsFor(from, card?.dataset.id || "");
  if (!targets.length) return false;
  moving.update(() => ({ m: { bio, from, card: card?.dataset.id || "", targets, at: 0 } }));
  return true;
}

function finish(m: NonNullable<Moving>): void {
  const t = m.targets[m.at];
  moving.update(() => ({ m: null }));
  if (!t) return;
  if (t.kind === "square") return offerJoin(t.name, m.bio, m.from);
  if (m.card) return void moveToTier(m.card, t.name);
  offerIntoTier(t.name, m.bio, m.from);
}

export function useBlockKeys(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const m = moving.get().m;
      if (m) {
        const step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
        if (step) moving.update(() => ({ m: { ...m, at: (m.at + step + m.targets.length) % m.targets.length } }));
        else if (e.key === "Enter") finish(m);
        else if (e.key === "Escape") moving.update(() => ({ m: null }));
        else return;
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      const el = document.activeElement as HTMLElement | null;
      if (e.ctrlKey || e.metaKey || e.altKey || studio.get().section !== "agents" || !el?.closest?.(".rc-scroll")) return;
      if (e.key.toLowerCase() === "m" && !e.shiftKey && start(el)) return e.preventDefault(), e.stopPropagation();
      const agent = el.closest<HTMLElement>('[data-testid="block-agent"]');
      const block = el.closest<HTMLElement>('[data-testid="block"]');
      if ((e.key === "Delete" || e.key === "Backspace") && block?.dataset.ref) {
        e.preventDefault();
        e.stopPropagation();
        selectBlock(block.dataset.ref);
        if (agent?.dataset.bio) askOut(agent.dataset.bio), select(block.dataset.ref, "agents");
        else select(block.dataset.ref, "remove");
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);
}
