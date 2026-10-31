// What each Local page holds (`about`, one line) and how to use it (`help`, a
// few short lines), 3.3.5.0 R1 (the Local section, docs/STUDIO-local.md);
// routes/help.ts merges them into HELP. Each page's head shows its `about` and,
// behind "How this page works", its own lines and the shared ones (the five ideas).
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

/** Local's five ideas, named on every page (plans/ROADMAP.md "Across every round of Local"). */
export const FIVE_IDEAS = [
  "The fit meter: a small green-to-red bar wherever a model is named, for 'will this run here at this window'.",
  "Why on every number: each figure carries its source and a one-line cause as its title.",
  "Intents, not model names: code, chat, long documents, images, embed rank the models by fit for this card.",
  "Make it fit: the fit planner's chosen option applied in one click, Undo beside it.",
  "The hub as the one picture: every machine sees the same hosts, profiles, traffic and samples through the fleet hub.",
];

function page(about: string, ...own: string[]): Help {
  return { about, help: lines(...own, ...FIVE_IDEAS) };
}

export const LOCAL_HELP: Record<string, Help> = {
  "local-resources": page("This machine's GPU, VRAM, RAM, CPU and temperature once a second, and every call to every local server as it happens.",
    "Each host has a strip: the VRAM bar names what holds most of the card (a model from /api/ps, or a process nvidia-smi names), the GPU line is the last minute.",
    "The sampler runs while this page is open (and while the steward job runs); hover a number for where it came from.",
    "The traffic view is the ledger as a stream, newest at the foot: one row per call, the steward's server events as muted rows; Follow keeps the newest in view.",
    "Filters narrow it by host, model, the machine that called and the kind; the sparklines count the calls per minute, a trim or a cut marked."),
  "local-hosts": page("Every server Halo knows: its address, kind, version, what is loaded, its card, its profiles, who calls it, and the controls its kind allows.",
    "Load warms a model at its profile's window (a generate with no prompt); Unload sends keep_alive 0; keep-alive picks how long a Load keeps it.",
    "A host another machine serves loads through the fleet member that serves it, as its owner allows (fleet.allow_control); otherwise the button says why not.",
    "Make it fit applies the fit planner's chosen option (a window per model, one at a time) as steward profiles; Undo puts them back.",
    "A server Find or Scan found that is not configured has Add to hosts: Setup's own Ollama writer adds the ollama.hosts entry. Nothing here changes a server's settings."),
  "local-models": page("Every model each host has installed, with its card, its fit meter, the roles it can hold, and the intent filter.",
    "Pick an intent on top (code, chat, long documents, images, embed): the rows are ranked by fit for this card and that intent, and one line says why this order.",
    "A row's chips say what the model is; click how Halo calls it for the exact way it is called; a role it cannot hold says why.",
    "Use as default saves it as the model a session starts on (Setup's save); a model that cannot orchestrate offers Make it the coder lane (the local-coder lineup).",
    "A row's ... menu: Show (/api/show's facts beside the card), Load now or Unload, Make a tuned twin (a window picked; a manifest, no new blobs), Copy, Rename, Delete. Each item's title is the halo models line that does the same.",
    "Delete shows what uses the model first (lineups, roles, the default and compaction models, profiles, live sessions); Delete anyway works whenever no session is on it.",
    "Loaded now on top lists what each host holds in memory, its VRAM share and when it unloads, with Unload; Jobs lists the pulls running, each with Cancel."),
  "local-library": page("Browse what could be installed: Ollama's library and the Hugging Face Hub, each row with its card and a fit badge for the host and window you pick.",
    "The strip on top is the host every row is worked out on: its GPU, usable and free VRAM, disk free and what is resident. The preset buttons (Coder, Reasoner, Bulk worker, Compactor, Verifier, Security, Multimodal, Embeddings, Offline-only) open their filters, shown and editable; Save as role template writes them as a local-<preset> lineup.",
    "Every capability carries its truth: ✓ verified (the battery probed it on this host), ◇ declared (the metadata says it), ≈ expected (the family, size or name), ? needs a probe. Only verified makes a model role-ready: each row says fits and role-ready side by side, and its cost: the download and its time, VRAM at the window, the cold load, tok/s and what it evicts.",
    "Download and verify pulls the model, runs the battery on it and offers it the role; nothing downloads until you press it. A model that crashed on this host shows why; Exclude crashed greys it and puts it last.",
    "Search, pick the source (Ollama, Hugging Face or both), the host the badge is worked out on and the window: every badge follows both.",
    "The badge is fits, tight, spill or no; hover it for the numbers: the weights and the KV cache at that window against the card's free memory, an estimate until the model is pulled.",
    "The intent filter ranks the rows for code, chat, long documents, images or embed; the filters keep what fits this host, a size, a family, a capability, a quantization, a licence.",
    "Click a name for its card's how lines and its other tags or files, each with its own fit. Pull puts it on the host picked (a progress bar and Cancel while it runs; installed on <host> after); Copy puts the pull line on the clipboard (halo models browse prints the same rows).",
    "Pull by name takes any name Ollama can pull: a library tag (qwen3.5:9b) or a Hugging Face GGUF (hf.co/<repo>:<quant>). A pull is the server's job: it goes on when this page closes, and Jobs lists it.",
    "The Ollama list is the shipped snapshot (its date shown) until Refresh reads ollama.com; the cache keeps the catalog a day and a hub search an hour."),
  "local-huggingface": page("The Hugging Face models on this machine's disk: each huggingface.model_dirs folder, what is in it, and the local servers Halo starts for them.",
    "Add folder puts a folder on huggingface.model_dirs; Forget takes it off (nothing on disk moves). Each model shows its kind, size, card and the fit meter on the host and window picked on top.",
    "A download starts from Library: a Hugging Face row's Download shows the repo's licence line and its files first, then the bytes go into the folder picked through the hub cache (models--<org>--<name>), with progress, Cancel and resume.",
    "Serve shows each flag before Start and where it comes from: the window (-c) and the layers on the GPU (-ngl) from the fit planner on this machine's card, one slot (-np), the card's KV cache type. It starts llama-server (mlx_lm.server on a Mac) on a loopback port.",
    "A running server is a host on Local -> Hosts and hf:local/<model> in the model lists; Use as default makes it the model a session starts on. Log shows the tail of its log, Stop ends it (terminate, then kill after 10 s).",
    "Halo's servers stop when the last Halo process on this home exits, unless keep was ticked. Delete shows what names the model first (roles, lineups, the default and compaction models, huggingface.local_servers) and waits while a server serves it."),
  "local-logs": page("Each host's Ollama server log, read-only: whether it is live, the last load of each model as the log says it, this session's truncations, the errors and crashes, and the newest lines.",
    "Pick the host on top. The status line says live, stale, quiet, unreadable, on that machine (no ssh entry) or missing, with the path; Copy puts the tail command on the clipboard.",
    "A host another machine serves is read over its ssh: entry (ollama.hosts); with none, a fleet member's push carries its events, else only /api/ps says the fit.",
    "Per model: the last load (layers on the GPU, where the KV cache sits, the graph splits, tok/s), the prompts the log cut this session, the error lines with times, crashed here with the fingerprint.",
    "The newest lines take a filter: fit, headroom, truncation, failure or all; Live reads them again every 5 seconds while the page is shown.",
    "More detail needs OLLAMA_DEBUG=1 on that machine and a restart there: Halo says how and never sets it, and it still does not log request bodies."),
  "local-benchmarks": page("Each model's speed card measured on its host, the tuning report for the whole host, and every change Halo made with its scope and Revert.",
    "Bench says its cost first (local: minutes of a busy card, never dollars), then loads the model cold, warms it untimed and times one prompt of about 60 % of each window (8k, 32k, the planner's ceiling) with a 256-token reply.",
    "Each row: the cold load, the reply tok/s per window, the largest window that stayed on the GPU (the planner's number beside it when they differ), the reply reserve below which replies were cut, the Ollama version it was measured on; a newer Ollama or a changed tag marks it stale.",
    "A bench waits while the host answered a call in the last minute or a session uses it; it needs the card to itself.",
    "The tuning report: the warm set that fits together and what a pivot costs, each model's window alone, beside the warm set and with q8_0 KV, the reserve, the steward's findings. Halo-side options have Apply; server-side ones show the exact line and its revert, for you to run.",
    "Every change has a scope: keep, until halo exits, until the session ends. Revert puts one back and says what it put back; halo local changes and halo local revert do the same."),
  "local-steward": page("Framed for 3.3.5.0 R6: the steward's chat and the scheduling of several local models on one card; today its status and last note.",
    "halo ollama steward status says the same from a terminal; Fleet's Ollama panel has its findings with Apply and Dismiss."),
};
