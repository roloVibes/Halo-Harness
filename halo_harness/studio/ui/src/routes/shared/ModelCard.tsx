// The model card in Studio (3.3.5.0 R0b; studio/model_card_api.py): what a
// model IS -- think, tools, vision, its purpose, its window -- as chips on a
// row (CardChips), the exact way Halo will call it and the roles it can hold
// as the row's expandable detail (CardDetail, data-testid=model-card), and,
// for the model picked as the main one, ModelCardPanel: the card read again
// (GET models/card), the fit meter, and when it cannot orchestrate here the
// one plain line with the offer -- keep it as the coder lane under an
// orchestrator (POST models/lane writes the lineup and makes it active;
// data-testid=model-offer-lane) -- or go ahead anyway, which needs nothing.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../../lib/ui";
import { FitMeter, type Fit } from "../../lib/ui/FitMeter";
import type { FitEvidenceView } from "./FitEvidence";
import { CardBlocks, type CardBlocksView } from "./ModelCardBlocks";

export type CardView = {
  chips: Record<string, string>;
  how: string[];
  /** 3.3.5.0 R4: what the server log said about it (providers/model_card_quirks.py). */
  quirks?: { kind: string; say: string }[];
  fit_for: Record<string, boolean>;
  fit_why: Record<string, string>;
  purpose?: string;
  thinks?: string;
  tools?: string;
  vision?: boolean;
  kind?: string;
  window?: { tokens: number | null; source?: string };
  /** 3.3.6.0 R1: the battery's profile in words (providers/model_card_blocks.py), each role's mark, the probe. */
  blocks?: CardBlocksView;
  fit_source?: Record<string, "verified" | "expected">;
  system_role?: string | null;
  speed?: { tok_s?: number | null; ttft_ms?: number | null; cold_load_s?: number | null; at_window?: number | null } | null;
  probe?: { date: string; at: number; line: string; agentic_ready: boolean; interactive: string; quirks: string[]; sits: string; stale: boolean } | null;
  /** 3.3.6.0 R3: the last load on its host as the server log says it (providers/fit_evidence.py). */
  fit_evidence?: FitEvidenceView | null;
};
export type CardFields = { card?: CardView; fit?: Fit };
type Offer = { lineup: string; coder: string; orchestrator: string; why: string; command: string };
type Check = { line: string; offer: Offer | null; offer_line: string };
type CardAnswer = CardFields & { ref: string; check: Check | null };

const ORDER = ["think", "tools", "vision", "purpose", "window"];
const ROLE_WORDS: Record<string, string> = { orchestrator: "orchestrator", coder: "coder lane", reviewer: "reviewer", small: "small", eyes: "eyes" };

export function CardChips({ card }: { card?: CardView }) {
  if (!card) return null;
  return (
    <span className="mcard-chips" data-testid="model-card-chips">
      {ORDER.filter((k) => card.chips?.[k]).map((k) => (
        <span key={k} className="og-chip mono mcard-chip" data-chip={k} data-value={card.chips[k]}
              title={k === "window" ? `window ${card.window?.tokens ?? "?"} (${card.window?.source || "unknown"})` : undefined}>
          {card.chips[k]}
        </span>
      ))}
    </span>
  );
}

export function CardDetail({ card, refName, open }: { card?: CardView; refName: string; open?: boolean }) {
  if (!card) return null;
  return (
    <details className="mcard" data-testid="model-card" data-ref={refName} open={open}>
      <summary className="mono muted">how Halo calls it</summary>
      <ul className="mcard-how mono" data-testid="model-card-how">
        {card.how.map((h) => <li key={h}>{h}</li>)}
      </ul>
      <div className="mcard-roles mono" data-testid="model-card-roles">
        {Object.entries(card.fit_for || {}).map(([role, ok]) => (
          <span key={role} className="mcard-role" data-role={role} data-ok={ok || undefined} data-mark={card.fit_source?.[role]}
                title={(ok ? "" : card.fit_why?.[role] || "") + (card.fit_source?.[role] === "verified" ? " (verified: probed)" : " (expected)")}>
            {ok ? "✓" : "·"} {ROLE_WORDS[role] || role}
          </span>
        ))}
      </div>
      <CardBlocks blocks={card.blocks} />
    </details>
  );
}

/** The picked model's card with the fit meter and, when it cannot orchestrate, the line and the lane offer. */
export function ModelCardPanel({ refName, offer = true, onLane }: { refName: string; offer?: boolean; onLane?: () => void }) {
  const [got, setGot] = useState<CardAnswer | null>(null);
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setGot(null);
    setSaid(null);
    if (!refName) {
      return;
    }
    let live = true;
    api.get<CardAnswer>(`models/card?ref=${encodeURIComponent(refName)}`).then((r) => {
      if (live) setGot(r);
    }, () => {
      if (live) setGot(null);
    });
    return () => {
      live = false;
    };
  }, [refName]);
  if (!refName || !got) return null;
  const lane = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ lines: string[] }>("models/lane", { ref: refName });
      setSaid({ ok: true, text: (r.lines || []).join(" · ") });
      onLane?.();
    } catch (e) {
      setSaid({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };
  const check = got.check;
  return (
    <div className="mcard-panel" data-testid="model-card-panel" data-ref={refName}>
      <div className="mcard-head">
        <span className="mono">{refName}</span>
        <CardChips card={got.card} />
        <FitMeter fit={got.fit} />
      </div>
      <CardDetail card={got.card} refName={refName} open />
      {offer && check && (
        <div className="mcard-check" data-testid="model-check">
          <span className="mcard-line" data-testid="model-check-line">{check.line}</span>
          {check.offer ? (
            <span className="mcard-offer">
              <Button size="sm" variant="primary" disabled={busy || !!said?.ok} onClick={() => void lane()} data-testid="model-offer-lane"
                      title={`writes lineup '${check.offer.lineup}' (${check.offer.coder} as the coder, ${check.offer.orchestrator} as main) and makes it active`}>
                {busy ? "Writing..." : `Keep it as the coder lane under ${check.offer.orchestrator}`}
              </Button>
              <span className="muted">or go ahead anyway: it is saved as it is</span>
            </span>
          ) : <span className="muted">{check.offer_line}</span>}
        </div>
      )}
      {said && <div className="mcard-said mono" data-ok={said.ok || undefined} data-testid="model-offer-said">{said.text}</div>}
    </div>
  );
}
