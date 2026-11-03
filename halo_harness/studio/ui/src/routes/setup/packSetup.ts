// A pack's own Setup blocks (3.3.11.0 R3, studio/setup_packs_api.py; docs/STUDIO-setup.md "A pack's blocks"): the
// enabled packs' `contributes.setup` arrive in the state's `packs`, each block a step of its own whose id is
// `pack:<id>:<block>`. A block with `after` is placed right behind that core step; the rest follow the core steps,
// grouped by pack, before the Summary. A form saves through the pack's config route (PackForm), a note is
// dismissed, a check runs through the Check job; any block can be skipped. With no pack contributing setup, the
// steps are the core ones, unchanged.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";
import { startCheck } from "./checkStore";
import { adoptAnswer, type SetupData } from "./store";

export type PackField = { key: string; type: string; enum: unknown[] | null; help: string; default: unknown; value: unknown };
export type PackBlock = {
  key: string;
  id: string;
  title: string;
  kind: "form" | "check" | "note";
  after: string;
  help: string;
  state: "" | "done" | "skipped";
  at: string;
  fields?: PackField[];
  values?: Record<string, unknown>;
  config_key?: string;
  what?: string;
  cost?: string;
  time?: string;
  writes?: string;
  text?: string;
};
export type PackSetup = { id: string; name: string; help: string; blocks: PackBlock[] };
export type Found = { pack: PackSetup; block: PackBlock };

export const PACK_PREFIX = "pack:";

export function isPackStep(s: string): boolean {
  return String(s || "").startsWith(PACK_PREFIX);
}

/** Every enabled pack's blocks, in the packs' order then the manifest's. */
export function packBlocks(d: SetupData | null): Found[] {
  return (d?.packs || []).flatMap((pack) => pack.blocks.map((block) => ({ pack, block })));
}

export function blockOf(d: SetupData | null, key: string): Found | null {
  return packBlocks(d).find((f) => f.block.key === key) || null;
}

export function blockPath(key: string): string {
  const [, pack, block] = key.split(":");
  return `setup/packs/${pack}/${block}`;
}

export const blockDone = (b: PackBlock) => b.state === "done" || b.state === "skipped";
export const blockWord = (b: PackBlock) => (b.state === "done" ? "done" : b.state === "skipped" ? "skipped" : "waiting");

/** The rail's list: `core` (the core steps, Summary last) with each pack block placed -- behind its `after` step
 *  when that step is in the list, else after the core steps, before the Summary. */
export function placeSteps(core: string[], d: SetupData | null): string[] {
  const found = packBlocks(d);
  if (!found.length) return core;
  const behind: Record<string, string[]> = {};
  const tail: string[] = [];
  for (const { block } of found) {
    if (block.after && core.includes(block.after)) (behind[block.after] ||= []).push(block.key);
    else tail.push(block.key);
  }
  const out: string[] = [];
  for (const s of core) {
    if (s === "summary") out.push(...tail);
    out.push(s, ...(behind[s] || []));
  }
  if (!core.includes("summary")) out.push(...tail);
  return out;
}

// -- a block's actions -----------------------------------------------------------------------------------------
type Act = { busy: string; last: Record<string, { ok: boolean; lines: string[] }> };
export const packAct = createStore<Act>({ busy: "", last: {} });

export function usePackAct<S>(select: (s: Act) => S): S {
  return useStore(packAct, select);
}

function said(key: string, ok: boolean, lines: string[]): void {
  packAct.update((s) => ({ last: { ...s.last, [key]: { ok, lines } } }));
}

/** POST the block: a note dismissed, a check started (its frames on the Check job), `{skip: true}` for any. */
export async function postBlock(key: string, body: Record<string, unknown> = {}): Promise<boolean> {
  packAct.update(() => ({ busy: key }));
  try {
    const r = await api.post<SetupData & { lines?: string[]; job?: unknown }>(blockPath(key), body);
    if (r && "job" in r) {
      said(key, true, []);
      void startCheck(); // the job's frames: the Check store polls them, this page and the Check page show them
      return true;
    }
    const { lines, ...data } = r;
    adoptAnswer(data as SetupData);
    said(key, true, lines || []);
    return true;
  } catch (e) {
    said(key, false, e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)]);
    return false;
  } finally {
    packAct.update(() => ({ busy: "" }));
  }
}
