// One model on Local -> Models (3.3.5.0 R1): its card's chips (think, tools,
// vision, the purpose, the window), the fit meter on this host's card (idea 1),
// its size and whether it is loaded, the steward profile's window and reserve,
// the roles it can hold (a role it cannot hold says why as its title), the card's
// `how` lines unfolded on click, "Use as default" (Setup's own save: setup/config
// model) and, when it cannot orchestrate here but can be a coder, "Make it the coder lane" (R0b's
// offer: POST models/lane writes the local-coder lineup and makes it active).
import { Button, FitMeter } from "../../lib/ui";
import { CardChips, CardDetail } from "../shared/ModelCard";
import { coderLane, gib, useAsDefault, useLocal } from "./store";
import type { ModelEntry } from "./types";

const ROLES: Record<string, string> = { orchestrator: "orchestrator", coder: "coder lane", reviewer: "reviewer", small: "small", eyes: "eyes" };

function Said({ k }: { k: string }) {
  const s = useLocal((st) => st.said[k]);
  return s ? <div className="mono lc-said" data-ok={s.ok || undefined} data-testid="local-said">{s.text}</div> : null;
}

export function ModelRow({ m, host, score }: { m: ModelEntry; host: string; score?: number | null }) {
  const busy = useLocal((s) => !!s.busy);
  const card = m.card || ({} as ModelEntry["card"]);
  const fitFor = card.fit_for || {};
  const p = m.profile;
  const laneOffer = fitFor.orchestrator === false && fitFor.coder !== false; // it cannot act here, it can write code
  return (
    <li className="lc-model" data-testid="local-model-row" data-model={m.model} data-host={host} data-fit={m.fit?.level || "unknown"}
        data-score={score ?? undefined} data-purpose={card.purpose || ""}>
      <div className="lc-model-top">
        <b className="mono">{m.model}</b>
        <CardChips card={m.card} />
        <FitMeter fit={m.fit} />
        <span className="spacer" />
        {m.size ? <span className="mono muted" title="the model's size on disk (/api/tags)">{gib(m.size)}</span> : null}
        {m.loaded && <span className="og-chip mono" data-testid="local-model-loaded" title={`${gib(m.loaded.size_vram)} on the GPU`}>loaded</span>}
      </div>
      <div className="lc-model-mid mono muted">
        {p && (p.num_ctx || p.num_predict) ? (
          <span data-testid="local-model-profile" title={p.note || "the steward profile (ollama.profiles)"}>
            {p.num_ctx ? `window ${p.num_ctx.toLocaleString("en-US")}` : ""}{p.num_predict ? ` · reserve ${p.num_predict.toLocaleString("en-US")}` : ""} (by {p.by || "you"})
          </span>
        ) : (
          <span>no profile: the window is {card.window?.tokens ? `${card.window.tokens.toLocaleString("en-US")} (${card.window.source})` : "the server's"}</span>
        )}
        <span className="lc-roles" data-testid="local-model-roles">
          {Object.entries(fitFor).map(([role, ok]) => (
            <span key={role} className="lc-role" data-role={role} data-ok={ok || undefined} title={ok ? `can hold ${ROLES[role] || role}` : card.fit_why?.[role]}>
              {ok ? "✓" : "·"} {ROLES[role] || role}
            </span>
          ))}
        </span>
      </div>
      <CardDetail card={m.card} refName={m.ref} />
      <div className="lc-model-acts">
        <Button size="sm" disabled={busy} onClick={() => void useAsDefault(m.ref)} data-testid="local-use-default" title={`model = ${m.ref} (Setup's save)`}>
          Use as default
        </Button>
        {laneOffer && (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void coderLane(m.ref)} data-testid="local-coder-lane"
                  title={card.fit_why?.orchestrator || "it cannot orchestrate here"}>
            Make it the coder lane
          </Button>
        )}
        <Said k={`default|${m.ref}`} />
        <Said k={`lane|${m.ref}`} />
      </div>
    </li>
  );
}
