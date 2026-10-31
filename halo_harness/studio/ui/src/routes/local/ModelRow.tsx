// One model on Local -> Models (3.3.5.0 R1): its card's chips (think, tools,
// vision, the purpose, the window), the fit meter on this host's card (idea 1),
// its size and whether it is loaded, the steward profile's window and reserve,
// the roles it can hold (a role it cannot hold says why as its title), the card's
// `how` lines unfolded on click, "Use as default" (Setup's own save: setup/config
// model) and, when it cannot orchestrate here but can be a coder, "Make it the coder lane" (R0b's
// offer: POST models/lane writes the local-coder lineup and makes it active). 3.3.5.0 R3: the actions menu
// (`local-model-acts`): Show, Load now / Unload, Make a tuned twin, Copy, Rename, Delete -- each row's title is
// the `halo models` line that does the same; a host this Studio cannot control has them disabled with the reason.
// 3.3.5.0 R4: "warm" / "cold (~N s to load)", "cache reused N %" and a card quirk ("re-reads the whole prompt every turn").
// 3.3.6.0 R1: where it sits (the battery's placement chip), "probed <date> · re-probe", the twin chips, the Probe
// action with its progress strip (ProbeBits.tsx); the detail adds the card's four blocks (shared/ModelCardBlocks.tsx).
import { Button, FitMeter, Menu } from "../../lib/ui";
import { CardChips, CardDetail } from "../shared/ModelCard";
import { SitsChips } from "../shared/ModelCardBlocks";
import { ProbeAction, ProbedMark, ProbeStrip, TwinChips } from "./ProbeBits";
import { line, openAct } from "./ctl";
import { coderLane, gib, loadModel, loadModels, unloadModel, useAsDefault, useLocal } from "./store";
import type { ModelEntry } from "./types";

function Acts({ m, host }: { m: ModelEntry; host: string }) {
  const ctl = useLocal((s) => s.hosts?.find((h) => h.name === host)?.controls);
  const off = ctl && !ctl.ok ? ctl.why : "";
  const row = (id: string, label: string, title: string, run: () => void, needs = true) => ({
    id, label, title: needs && off ? off : title, disabled: needs && !!off, testid: "local-act", data: { act: id }, run });
  const load = async () => {
    await (m.loaded ? unloadModel(host, m.model) : loadModel(host, m.model));
    void loadModels();
  };
  return (
    <Menu icon="more" label={`actions on ${m.model}`} title="Show, load, twin, copy, rename, delete" testid="local-model-acts" menuTestid="local-model-menu"
          btnClass="icon-btn" align="right" width={260} groups={[{ rows: [
            row("show", "Show", line("show", host, m.model), () => openAct("show", host, m)),
            m.loaded ? row("unload", "Unload", line("unload", host, m.model), () => void load())
                     : row("load", "Load now", line("load", host, m.model), () => void load()),
            row("twin", "Make a tuned twin", line("twin", host, m.model, "--window", "N"), () => openAct("twin", host, m)),
            row("copy", "Copy", line("copy", host, m.model, "<new name>"), () => openAct("copy", host, m)),
            row("rename", "Rename", line("rename", host, m.model, "<new name>"), () => openAct("rename", host, m)),
            row("delete", "Delete", line("rm", host, m.model), () => openAct("delete", host, m)),
          ] }]} />
  );
}

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
        <SitsChips blocks={card.blocks} />
        <FitMeter fit={m.fit} />
        <TwinChips m={m} host={host} />
        <span className="spacer" />
        {m.size ? <span className="mono muted" title="the model's size on disk (/api/tags)">{gib(m.size)}</span> : null}
        {m.loaded && <span className="og-chip mono" data-testid="local-model-loaded" title={`${gib(m.loaded.size_vram)} on the GPU`}>loaded</span>}
        {m.warm && <span className="og-chip mono" data-testid="local-model-warm" data-state={m.warm.state}
                         title="warm: loaded now; cold: the next call loads it first (the last load the traffic ledger saw)">{m.warm.line}</span>}
        {m.warm?.cache_line && <span className="mono muted" data-testid="local-model-cache"
                                     title="the newest turn's share of the prompt Ollama did not read again">{m.warm.cache_line}</span>}
        {m.ref.startsWith("ol:") && <ProbedMark m={m} host={host} />}
        {m.crashed && <span className="og-chip mono ls-crash-chip" data-testid="local-model-crashed" data-signature={m.crashed.signature}
                            title={`${m.crashed.line} (halo ollama crashes)`}>crashed here</span>}
        {(card.quirks || []).map((q) => <span key={q.kind} className="og-chip mono" data-testid="local-model-quirk" data-kind={q.kind} title={q.say}>{q.kind === "no-prompt-cache" ? "re-reads the whole prompt every turn" : q.kind}</span>)}
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
      {m.ref.startsWith("ol:") && <ProbeStrip m={m} host={host} />}
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
        <span className="spacer" />
        {m.ref.startsWith("ol:") && <ProbeAction m={m} host={host} />}
        {m.ref.startsWith("ol:") && <Acts m={m} host={host} />}
        <Said k={`default|${m.ref}`} />
        <Said k={`lane|${m.ref}`} />
        <Said k={`${host}|${m.model}`} />
      </div>
    </li>
  );
}
