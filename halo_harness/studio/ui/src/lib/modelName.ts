// The resolved model id without its provider prefix (3.3.15.0 L1, the Instrument look's "model names" note): what a
// map node, a Roles Live node and a Live tag show. The full id (`or:qwen/qwen3-coder`, `ol:qwen3:30b@gpu-box`) stays
// in the inspector, the Agent panel and the tooltips. The prefixes are Halo's route words (halo_harness/model.py
// parse_model_ref; studio/models_fallback.py _PREFIX): or, ol, dbx, db, ant, oai, hf, xp. An Ollama tag keeps its
// `:size` (`qwen3:30b`), a host after `@` goes, and a vendor path keeps its last part (`qwen/qwen3-coder` ->
// `qwen3-coder`, `hf:local/Qwen2.5-7B@box` -> `Qwen2.5-7B`). A name without a known prefix is only trimmed of its path.
const PREFIX = /^(or|ol|dbx|db|ant|oai|hf|xp):/;

export function shortModel(id: string | null | undefined): string {
  const raw = String(id || "").trim();
  if (!raw) return "";
  const bare = raw.replace(PREFIX, "").split("@")[0];
  return bare.split("/").filter(Boolean).pop() || bare;
}
