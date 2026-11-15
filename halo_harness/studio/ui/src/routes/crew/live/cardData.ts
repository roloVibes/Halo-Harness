// The run report card's data and words (3.4.1.0 R3 "Time"): what `GET replays/report?ref=` answers (live/report_card.py
// builds it from the run's record, no model call; its Markdown comes with it, the text `halo report` prints), read once per
// card. The words mirror live/compare_text.py and live/report_card_text.py, so the page and the Markdown say the same: a
// cost Halo cannot price is "unknown" or the priced part with a "+", never $0.
import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { toast } from "../../../lib/store";
import type { Cell } from "./compareStore";

export type Step = { t: number; at: string; kind: string; text: string };
export type Phase = { phase: string; words: string; secs: number; share: number | null };
export type Block = { block: string; agents: number; secs: number; busy: number };
export type ModelCost = { model: string; cost_usd: number | null; share: number | null; unknown: boolean };
export type BlockCost = { block: string; cost_usd: number; unknown: boolean };
export type Fail = { t: number; at: string; who: string; next: string };
export type Wait = { t: number; at: string; who: string; text: string; secs: number | null };
export type ModelDid = { model: string; cost_share: number | null; time_share: number | null; agents: { name: string; role: string; task: string }[] };
export type Artefact = { rel: string; by: string[]; outside?: boolean };
export type Card = {
  format: string; kind: "session" | "run" | "file" | string; id: string; ref: string; title: string; when: string; halo: string; file: string | null;
  how: string; ok: boolean | null; cells: Record<string, Cell>; story: Step[]; story_more: number;
  time: { wall_s: number | null; phases: Phase[]; blocks: Block[] };
  money: { total: number | null; known: boolean; unknown: string[]; models: ModelCost[]; blocks: BlockCost[] };
  failures: Fail[]; failed_calls: number; retries: number | null; waits: Wait[]; waited_s: number;
  models: ModelDid[]; artefacts: Artefact[] | null; cannot: string[];
};
export type Got = { card: Card | null; markdown: string; error: string };

/** The card of `ref` (session:<id> | run:<id> | file:<id>), read when the ref changes. */
export function useCard(ref: string): Got {
  const [got, setGot] = useState<Got & { ref: string }>({ ref: "", card: null, markdown: "", error: "" });
  useEffect(() => {
    let live = true;
    api.get<{ card: Card; markdown: string }>("replays/report", { ref })
      .then((r) => live && setGot({ ref, card: r.card, markdown: r.markdown, error: "" }))
      .catch((e) => live && setGot({ ref, card: null, markdown: "", error: e instanceof ApiError ? e.message : String(e) }));
    return () => {
      live = false;
    };
  }, [ref]);
  return got.ref === ref ? got : { card: null, markdown: "", error: "" };
}

/** "1 min 40 s", "16 s", "unknown" (live/compare_text.secs). */
export function secs(v: number | null | undefined): string {
  if (v === null || v === undefined || !isFinite(v)) return "unknown";
  const s = Math.round(v);
  if (s >= 3600) return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")} min`;
  return s >= 60 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s` : `${s} s`;
}

/** "$0.0300"; with `unknown`: the priced part with a "+", or "unknown (no price)" -- never $0. */
export function usd(v: number | null | undefined, unknown = false): string {
  const known = typeof v === "number" && isFinite(v);
  if (unknown) return known && v ? `${usd(v)}+` : "unknown (no price)";
  if (!known) return "unknown";
  return v >= 1 ? `$${v.toFixed(2)}` : `$${v.toFixed(4)}`;
}

export const pct = (x: number | null | undefined): string => (x === null || x === undefined ? "?" : `${Math.round(x * 100)} %`);
export const bare = (ref: string): string => String(ref).slice(String(ref).indexOf(":") + 1).split("/").pop() || String(ref);

/** The card's Markdown on the clipboard (the same text `halo report` prints). */
export function copyMarkdown(text: string): void {
  try {
    navigator.clipboard.writeText(text).then(() => toast("Report card copied as Markdown", "done"),
      () => toast("The clipboard is closed to this page: halo report <id> prints the same Markdown", "error"));
  } catch {
    toast("The clipboard is closed to this page: halo report <id> prints the same Markdown", "error");
  }
}
