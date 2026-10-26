// setup-local (3.3.0.0 R2): the terminal wizard's Local models step. The
// model folders Halo scans for .gguf files and safetensors / MLX folders
// (`huggingface.model_dirs`: add one by typing its path, remove one), the
// runtime `halo local serve` prefers for a file it is not told one for
// (`huggingface.preferred_runtime`: llama-server or mlx_lm) and what is on
// this machine now (providers.local_models.detection_summary_lines), read
// again after every save.
import { useState } from "react";
import { Button } from "../../lib/ui";
import { useLoadState, Waiting } from "./BlockFoot";
import { CardLines, MiniForm, send, Table, useCards } from "./cards";
import { NONE, useSetup } from "./store";

function Runtime() {
  const saved = useSetup((s) => s.data?.local_models.runtime || "");
  const rows = useSetup((s) => s.data?.local_models.runtimes || NONE);
  const busy = useCards((s) => s.busy);
  const [picked, setPicked] = useState("");
  const shown = picked || saved;
  return (
    <div className="su-radios" role="radiogroup" aria-label="Preferred runtime" data-testid="setup-runtimes">
      {rows.map((r) => (
        <label key={r.id} className="su-radio" data-on={shown === r.id || undefined} data-testid="setup-runtime" data-id={r.id}>
          <input type="radio" name="setup-runtime" checked={shown === r.id} onChange={() => setPicked(r.id)} data-testid="setup-runtime-input" data-id={r.id} />
          <span className="su-radio-text">
            <span className="su-radio-label mono">{r.label}</span>
            <span className="su-radio-note muted">{r.note}</span>
          </span>
        </label>
      ))}
      <div className="su-card-row">
        <Button variant="primary" size="sm" disabled={!!busy || !picked || picked === saved} data-testid="setup-runtime-save"
                onClick={async () => { if (await send("local-runtime", "setup/runtime", { runtime: picked })) setPicked(""); }}>
          {busy === "local-runtime" ? "Saving..." : "Save runtime"}
        </Button>
        <span className="su-note muted mono">{saved ? `saved: ${saved}` : "not set: llama-server for GGUF, mlx_lm for safetensors on Apple Silicon"}</span>
      </div>
      <CardLines card="local-runtime" />
    </div>
  );
}

export function LocalModelsDetail() {
  const { ready, error } = useLoadState();
  const dirs = useSetup((s) => s.data?.local_models.model_dirs || NONE);
  const detection = useSetup((s) => (s.data?.local_models.detection || NONE).join("\n"));
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-local-models">
      <p className="su-lead muted">
        Folders Halo scans for .gguf files and safetensors / MLX model folders, on top of the Hugging Face cache, LM Studio's folder and
        Ollama's store.
      </p>
      <div className="su-sub mono">Model folders</div>
      <Table card="local-dir" head={["folder"]} rows={dirs.map((d) => ({ key: d, cells: [d] }))} wrap={0}
             onRemove={(path) => void send("local-dir", "setup/model-dir", { path, remove: true })} />
      {!dirs.length && <div className="su-note muted" data-testid="setup-dirs-empty">No folder added yet (huggingface.model_dirs is empty).</div>}
      <MiniForm card="local-dir" inputs={[{ id: "path", label: "Add a folder", placeholder: "/path/to/a/models/folder" }]} button="Add folder"
                onSave={(v) => send("local-dir", "setup/model-dir", { path: v.path || "" })} />
      <CardLines card="local-dir" />
      <div className="su-sub mono">Preferred runtime</div>
      <Runtime />
      <div className="su-sub mono">On this machine now</div>
      <pre className="su-detect mono" data-testid="setup-detection">{detection || "detecting..."}</pre>
    </div>
  );
}

export function LocalModelsGlance() {
  const n = useSetup((s) => s.data?.local_models.model_dirs.length || 0);
  const runtime = useSetup((s) => s.data?.local_models.runtime || "");
  return (
    <div className="glance">
      <div className="glance-kicker mono">LOCAL MODELS</div>
      <div className="glance-text">{n} folder{n === 1 ? "" : "s"}</div>
      <div className="glance-hint">runtime: {runtime || "not set"}</div>
    </div>
  );
}
