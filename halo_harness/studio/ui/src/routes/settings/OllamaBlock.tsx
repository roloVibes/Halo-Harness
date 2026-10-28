// Settings -> Ollama, the steward's block above the group's rows (3.3.4.0 R5): its status line (where the job
// runs, since when, the model it uses and why), the model picker (automatic = the key unset, "none" = no notes,
// or one of the local models this machine lists; writes ollama.steward.model), the mode (auto / review / off ->
// ollama.steward.apply), the job switch (ollama.steward.job, next launch) and "Open the Ollama panel". The
// thresholds (every_s, note_every_s, slow_tok_s, ledger, fleet.ollama.share) stay generic rows below it.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { openOllama } from "../fleet/Ollama";
import { loadSteward, useOllama } from "../fleet/ostore";
import { resetValue, setValue, useSettings } from "./store";

const MODES = [
  ["auto", "auto: apply the steward's changes, say one line"],
  ["review", "review: propose; Apply in the Ollama panel"],
  ["off", "off: findings only"],
];
const AUTO = "";

export function OllamaBlock() {
  useEffect(() => {
    void loadSteward();
  }, []);
  const st = useOllama((s) => s.steward);
  const model = useSettings((s) => s.values["ollama.steward.model"]);
  const apply = useSettings((s) => s.values["ollama.steward.apply"]);
  const job = useSettings((s) => s.values["ollama.steward.job"]);
  const busy = useSettings((s) => s.busy);
  const current = model?.set && typeof model.value === "string" ? model.value : AUTO;
  const refs = [...new Set([...(st?.models || []), ...(current && current !== "none" ? [current] : [])])];
  const mode = apply?.set ? String(apply.value) : "auto";
  const jobOn = job?.set ? job.value !== false : true;
  const saveModel = async (v: string) => {
    if (v === AUTO) await resetValue("ollama.steward.model");
    else await setValue("ollama.steward.model", v);
    void loadSteward();
  };
  const saveMode = async (v: string) => {
    await setValue("ollama.steward.apply", v);
    void loadSteward();
  };
  return (
    <section className="st-ollama" data-testid="settings-ollama-block" aria-label="The Ollama steward">
      <div className="st-ollama-row">
        <b>The Ollama steward</b>
        <span className="spacer" />
        <Button size="sm" onClick={openOllama} data-testid="settings-ollama-open">Open the Ollama panel</Button>
      </div>
      <div className="st-ollama-status mono muted" data-testid="settings-ollama-status">
        {(st?.status_lines || ["reading the steward..."]).map((l) => (
          <div key={l}>{l.trim()}</div>
        ))}
      </div>
      <label className="st-ollama-row">
        <span>Model</span>
        <select className="st-select mono" value={current} disabled={busy === "ollama.steward.model"} data-testid="settings-ollama-model"
                onChange={(e) => void saveModel(e.target.value)}>
          <option value={AUTO}>automatic{st?.status?.model && current === AUTO ? ` (now ${st.status.model})` : ""}</option>
          <option value="none">none: no notes (the rules still run)</option>
          {refs.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <span className="muted">the model that writes the notes; a local one costs nothing</span>
      </label>
      <label className="st-ollama-row">
        <span>Mode</span>
        <select className="st-select mono" value={mode} disabled={busy === "ollama.steward.apply"} data-testid="settings-ollama-mode"
                onChange={(e) => void saveMode(e.target.value)}>
          {MODES.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div className="st-ollama-row">
        <span>Job</span>
        <button type="button" role="switch" aria-checked={jobOn} className={"st-toggle" + (jobOn ? " on" : "")} data-testid="settings-ollama-job"
                disabled={busy === "ollama.steward.job"} onClick={() => void setValue("ollama.steward.job", !jobOn)}>
          <span className="st-toggle-knob" aria-hidden="true" />
          <span className="st-toggle-word mono">{jobOn ? "on" : "off"}</span>
        </button>
        <span className="muted">runs with Studio or the fleet hub; takes effect on the next launch</span>
      </div>
    </section>
  );
}
