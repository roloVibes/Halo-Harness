// The Inspector's MODEL strip (3.1.4.0 R4; the owner: "I can't figure out
// where the model drop down list is"): above the three tabs, whenever a
// lineup is open. With a card selected: "runs on: <model>" (what the card
// resolves to today, with the price and context its pill shows) and the
// ModelSelect bound to the card's own model (`models.preference`, saved at
// once; the first option keeps the bio's own), plus "change the bio's
// model" (the Bios panel on that bio, its MODELS section focused). With no
// card selected it shows the lineup's main card the same way. The card's
// model pill and Enter on a selected card focus this select.
import { useHelpGroup } from "../../lib/fieldHelp";
import { ModelSelect } from "../shared/ModelSelect";
import { shortRef } from "../shared/catalog";
import { focusDone, setSlotModel, showBioModels } from "./modelActions";
import { agentsOf, modelRow, nodeById, priceText, useRoles } from "./store";
import type { Raw } from "./types";

export function ModelStrip() {
  const raw = useRoles((s) => s.raw);
  const n = useRoles((s) => nodeById(s, s.sel));
  const main = useRoles((s) => s.graph?.nodes.find((x) => x.role === "main"));
  const card = n || main;
  const row = useRoles((s) => (card ? modelRow(s, card.model) || s.fallback.find((m) => m.ref === card.model) : undefined));
  const bioRow = useRoles((s) => (card ? s.bios.find((b) => b.name === card.agent) : undefined));
  const focus = useRoles((s) => s.modelFocus === "strip");
  const busy = useRoles((s) => s.busy === "save");
  const fallbackModel = useRoles((s) => s.info?.default_model || "");
  const h = useHelpGroup("model_select");
  if (!raw || !card) {
    return (
      <section className="msel-strip" data-testid="roles-model-strip" aria-label="The model">
        <div className="msel-strip-head">
          <span className="glance-kicker mono">MODEL</span>
          <span className="mono msel-runs" data-testid="roles-model-runs-on">runs on: <b>{fallbackModel ? shortRef(fallbackModel) : "the default model"}</b></span>
          <span className="mono muted">no lineup open: one model for everything</span>
        </div>
      </section>
    );
  }
  const entry = (agentsOf(raw)[card.index] || {}) as Raw;
  const own = String(((entry.models && typeof entry.models === "object" ? entry.models : {}) as Raw).preference || "");
  const bioModel = card.bio_model ?? bioRow?.model ?? "";
  return (
    <section className="msel-strip" data-testid="roles-model-strip" data-card={card.id} data-main={!n || undefined} aria-label="The model">
      <div className="msel-strip-head">
        <span className="glance-kicker mono">{n ? "MODEL" : "MODEL · MAIN CARD"}</span>
        <span className="mono msel-runs" data-testid="roles-model-runs-on" data-ref={card.model} title={h.runs_on}>
          runs on: <b>{card.model ? shortRef(card.model) : "no model resolves"}</b>
        </span>
        <span className="mono muted msel-price" title="price per 1M tokens in / out, and the context">{priceText(row)} · ctx {row?.context || card.context || "?"}</span>
        <button type="button" className="og-link mono msel-bio" onClick={() => showBioModels(card.agent)} disabled={!card.agent}
                title={`${h.bio || ""} (${card.agent || "no bio"})`} data-testid="roles-model-bio-link">
          change the bio's model
        </button>
      </div>
      <ModelSelect label={n ? `${card.alias || card.role}'s own model` : "the main card's own model"} hint={n ? h.card : h.main} value={own}
                   inherit={{ label: "the bio's own", model: bioModel }} onPick={(ref) => void setSlotModel(card.index, ref)}
                   testid="roles-model-select" focus={focus} onFocused={focusDone} busy={busy} compact bare />
    </section>
  );
}
