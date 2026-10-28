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
    "Use as default saves it as the model a session starts on (Setup's save); a model that cannot orchestrate offers Make it the coder lane (the local-coder lineup)."),
  "local-library": page("Framed for 3.3.5.0 R2: browse Ollama's library and the Hugging Face Hub, each row with a fit badge for this card.",
    "Until then halo models lists what the providers here have, and halo models show <ref> one model's card."),
  "local-huggingface": page("Framed for 3.3.5.0 R4: Hugging Face local models downloaded, served, stopped and deleted from here.",
    "Until then halo local --terminal shows the local servers and the model folders; halo local serve starts one."),
  "local-benchmarks": page("Framed for 3.3.5.0 R5: a measured battery per model on this card, tuning scans, and changes that revert when a session ends.",
    "Until then halo ollama calibrate <model> measures the largest window that stays on the GPU."),
  "local-steward": page("Framed for 3.3.5.0 R6: the steward's chat and the scheduling of several local models on one card; today its status and last note.",
    "halo ollama steward status says the same from a terminal; Fleet's Ollama panel has its findings with Apply and Dismiss."),
};
