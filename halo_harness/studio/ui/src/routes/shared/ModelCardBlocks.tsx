// The model card's four plain-language blocks (3.3.6.0 R1; providers/model_card_blocks.py): Use it for, Don't use
// it for, Where it sits (one placement chip: full agent, coder, reasoner, bulk worker · non-agentic, compactor, plus
// pivot-only / not interactive), Limits (window trained vs usable and whether verified, size, co-reside or pivot,
// measured tok/s, cold load). Every value carries its mark (3.3.6.0 R2: the three truths): verified (the battery
// probed it on this host), declared (the metadata says it) or expected (the family rules, the size, the name) --
// data-mark on each item, "declared" / "expected" said in words. 3.3.6.0 R4: the Measured block (each line "value
// (source, date, n)", providers/measured.py), the KV dial under the fit line ("f16 KV -> 32k, q8_0 KV -> 64k on this
// card", its crash note and the host-side action, providers/kv_dial.py) and How Halo talks to this model
// (DialectBlock.tsx, the dialect record, editable). 3.3.6.0 R5: "where it sits" names the largest window the bench saw
// stay on the GPU, and the KV dial's Halo-side half has Apply with a scope (KvApply.tsx).
import { DialectBlock, type DialectView } from "./DialectBlock";
import { FitEvidenceChip } from "./FitEvidence";
import { KvApply, type KvApplyView } from "./KvApply";

export type Mark = "verified" | "declared" | "expected";
export type BlockItem = { text: string; mark: Mark };
export type CardBlocksView = {
  use_for?: BlockItem[]; dont_use_for?: BlockItem[]; limits?: BlockItem[];
  sits?: { chip: string; chips: string[]; mark: Mark; gpu?: string };
  /** 3.3.6.0 R3: the fit line the server log cites (model_card_blocks.fit_block). */
  fit?: { text: string; mark: Mark; state: string; source?: string | null } | null;
  /** 3.3.6.0 R4 */
  measured?: BlockItem[];
  kv_dial?: { text: string; crash?: string; action?: string; in_force?: string; apply?: KvApplyView | null } | null;
  dialect?: DialectView | null;
};

const TITLES: [keyof CardBlocksView, string][] = [["use_for", "Use it for"], ["dont_use_for", "Don't use it for"], ["limits", "Limits"]];

export function SitsChips({ blocks }: { blocks?: CardBlocksView }) {
  const s = blocks?.sits;
  if (!s || !s.chip) return null;
  return (
    <span className="mprobe-sits" data-testid="model-card-sits" data-mark={s.mark}>
      {(s.chips || [s.chip]).map((c) => (
        <span key={c} className="og-chip mono mprobe-chip" data-chip={c} data-mark={s.mark}
              title={s.mark === "verified" ? "where it sits: the battery probed it on this host" : s.mark === "declared"
                ? "where it sits: from what the model declares (not probed yet)" : "where it sits: expected from its family or name (not probed yet)"}>
          {c}{s.mark !== "verified" ? " ?" : ""}
        </span>
      ))}
      {s.gpu && <span className="og-chip mono mprobe-chip" data-testid="model-card-gpu" title="the largest window the bench saw stay on the GPU">{s.gpu}</span>}
    </span>
  );
}

function KvDial({ k }: { k: NonNullable<CardBlocksView["kv_dial"]> }) {
  return (
    <div className="mono muted kv-dial" data-testid="model-card-kv-dial" title={k.action ? `${k.action} (KV in force: ${k.in_force})` : `KV in force: ${k.in_force}`}>
      {k.text}
      {k.crash && <div className="kv-crash" data-testid="model-card-kv-crash">{k.crash}</div>}
      {k.action && <div className="kv-action">to change it: {k.action}</div>}
      {k.apply && <KvApply a={k.apply} />}
    </div>
  );
}

export function CardBlocks({ blocks, refName = "" }: { blocks?: CardBlocksView; refName?: string }) {
  if (!blocks) return null;
  return (
    <div className="mprobe-blocks" data-testid="model-card-blocks">
      <div className="mprobe-block" data-testid="model-card-block" data-block="sits">
        <span className="rail-label mono">Where it sits</span> <SitsChips blocks={blocks} />
      </div>
      {blocks.fit && (
        <div className="mprobe-block" data-testid="model-card-block" data-block="fit">
          <span className="rail-label mono">Fit here</span>{" "}
          <FitEvidenceChip ev={{ state: blocks.fit.state, line: blocks.fit.text, source: blocks.fit.source }} testid="model-card-fit" />
          {blocks.kv_dial?.text && <KvDial k={blocks.kv_dial} />}
        </div>
      )}
      {!blocks.fit && blocks.kv_dial?.text && (
        <div className="mprobe-block" data-testid="model-card-block" data-block="kv">
          <span className="rail-label mono">KV cache</span> <KvDial k={blocks.kv_dial} />
        </div>
      )}
      {TITLES.map(([key, title]) => {
        const items = (blocks[key] as BlockItem[] | undefined) || [];
        if (!items.length) return null;
        return (
          <div key={key} className="mprobe-block" data-testid="model-card-block" data-block={key}>
            <span className="rail-label mono">{title}</span>
            <ul className="mprobe-items">
              {items.map((x) => (
                <li key={x.text} data-mark={x.mark} data-testid="model-card-item">
                  {x.text}{x.mark !== "verified" && <span className="muted"> ({x.mark})</span>}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {!!blocks.measured?.length && (
        <div className="mprobe-block" data-testid="model-card-block" data-block="measured">
          <span className="rail-label mono" title="each fact: its value (where it was measured, when, over how many calls)">Measured</span>
          <ul className="mprobe-items">
            {blocks.measured.map((x) => <li key={x.text} data-testid="model-card-measured">{x.text}</li>)}
          </ul>
        </div>
      )}
      <DialectBlock view={blocks.dialect} refName={refName} />
    </div>
  );
}
