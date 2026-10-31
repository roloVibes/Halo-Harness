// The model card's four plain-language blocks (3.3.6.0 R1; providers/model_card_blocks.py): Use it for, Don't use
// it for, Where it sits (one placement chip: full agent, coder, reasoner, bulk worker · non-agentic, compactor, plus
// pivot-only / not interactive), Limits (window trained vs usable and whether verified, size, co-reside or pivot,
// measured tok/s, cold load). Every value carries its mark: verified (the battery probed it on this host) or
// expected (the declared facts or the family rules) -- data-mark on each item, "expected" said in words.
export type BlockItem = { text: string; mark: "verified" | "expected" };
export type CardBlocksView = {
  use_for?: BlockItem[]; dont_use_for?: BlockItem[]; limits?: BlockItem[];
  sits?: { chip: string; chips: string[]; mark: "verified" | "expected" };
};

const TITLES: [keyof CardBlocksView, string][] = [["use_for", "Use it for"], ["dont_use_for", "Don't use it for"], ["limits", "Limits"]];

export function SitsChips({ blocks }: { blocks?: CardBlocksView }) {
  const s = blocks?.sits;
  if (!s || !s.chip) return null;
  return (
    <span className="mprobe-sits" data-testid="model-card-sits" data-mark={s.mark}>
      {(s.chips || [s.chip]).map((c) => (
        <span key={c} className="og-chip mono mprobe-chip" data-chip={c} data-mark={s.mark}
              title={s.mark === "verified" ? "where it sits: the battery probed it on this host" : "where it sits: expected from what the model declares (not probed yet)"}>
          {c}{s.mark === "expected" ? " ?" : ""}
        </span>
      ))}
    </span>
  );
}

export function CardBlocks({ blocks }: { blocks?: CardBlocksView }) {
  if (!blocks) return null;
  return (
    <div className="mprobe-blocks" data-testid="model-card-blocks">
      <div className="mprobe-block" data-testid="model-card-block" data-block="sits">
        <span className="rail-label mono">Where it sits</span> <SitsChips blocks={blocks} />
      </div>
      {TITLES.map(([key, title]) => {
        const items = (blocks[key] as BlockItem[] | undefined) || [];
        if (!items.length) return null;
        return (
          <div key={key} className="mprobe-block" data-testid="model-card-block" data-block={key}>
            <span className="rail-label mono">{title}</span>
            <ul className="mprobe-items">
              {items.map((x) => (
                <li key={x.text} data-mark={x.mark} data-testid="model-card-item">
                  {x.text}{x.mark === "expected" && <span className="muted"> (expected)</span>}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
