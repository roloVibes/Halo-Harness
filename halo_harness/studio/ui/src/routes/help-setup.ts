// What each Setup page's block is (`about`, one line) and how to use it (`help`, a
// few short lines), 3.3.0.0 R1 + R2 + R3 (the Setup section, docs/STUDIO-sections.md
// "Setup"); routes/help.ts merges them into HELP. 3.3.1.0 R1: each page's head shows its `about` and, behind
// "How this page works", its `help` (routes/setup/SetupPage.tsx); `setup-summary` is the Summary page.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

export const SETUP_HELP: Record<string, Help> = {
  "setup-providers": {
    about: "The providers this box calls: one card each, its key saved to the env file (~/.config/halo/env).",
    help: lines(
      "Paste a key and press Save & test: the key goes to the env file, the provider is turned on, its host probed and its model list read.",
      "A key is never shown again: the card says set, where it comes from and ****1234. Paste a new one to replace it.",
      "Ollama: add hosts by name and URL (a key for Ollama Cloud goes to the env file); the first host is the default. Under the card, Find, scan, add and measure opens the finders: Find Ollama servers asks this machine at once, Scan this network sweeps the network (10 s); tick what they list and Add the ticked, then Measure the found models.",
      "Hugging Face: the router token, dedicated endpoints and local servers, each added or removed on its own.",
      "The same as halo init's Providers tabs; halo providers lists them in a terminal.",
    ),
  },
  "setup-local": {
    about: "Model folders and the local runtime: huggingface.model_dirs and huggingface.preferred_runtime.",
    help: lines(
      "Add a folder by typing its path: Halo scans it for .gguf files and safetensors / MLX model folders (the same as /local add).",
      "The runtime is what halo local serve uses for a file it is not told one for: llama-server or mlx_lm.",
      "The lines at the foot say what is on this machine now, read again after each save.",
    ),
  },
  "setup-model": {
    about: "The model a new session starts on: model in ~/.halo/config.json.",
    help: lines(
      "The list is the catalog of the providers set up here, grouped by provider, with what each model is best at.",
      "Search narrows it by ref, name or best at; the saved one is checked.",
      "Pick one and Save: the same as halo config set model <ref>. halo --model and /model still pick another for one run.",
    ),
  },
  "setup-permissions": {
    about: "The permission mode new sessions start in: permission_mode in ~/.halo/config.json.",
    help: lines(
      "auto allows everything except your own deny and ask rules; acceptEdits applies file edits and asks for the rest;",
      "default asks before edits and other tools; plan researches and proposes before any change.",
      "Save writes it; Shift+Tab still cycles the mode inside a session.",
    ),
  },
  "setup-theme": {
    about: "The colours of halo in your terminal: theme in ~/.halo/config.json.",
    help: lines(
      "Each swatch is drawn in the colours the terminal uses for that theme; -daltonized and -ansi are the variants.",
      "Save writes it (the same as /theme in a session). Studio's own dark / light switch is a setting of this browser.",
    ),
  },
  "setup-team": {
    about: "The lineup new sessions run: team and roles.enabled in ~/.halo/config.json.",
    help: lines(
      "One model for everything: roles off, no lineup. auto (the default): each sub-task goes to a model picked for it.",
      "Any other lineup gives each job its own agent and model; the preview shows role -> agent -> model and the cost line.",
      "Apply writes what the terminal wizard's Team step writes; Edit in Roles opens the lineup in Roles.",
    ),
  },
  "setup-linux": {
    about: "The fixes a Linux box may be missing: a static rg in ~/.local/bin, ~/.local/bin on PATH for any shell.",
    help: lines(
      "Listed only when this box lacks one (never on Windows); Apply does what the terminal wizard's Linux step does.",
      "rg comes from ripgrep's own release page into ~/.local/bin; the PATH line goes into ~/.zshenv or ~/.profile, once.",
      "halo doctor lists the same two.",
    ),
  },
  "setup-check": {
    about: "Check this setup: the doctor, the model catalog, a hello on the default model, the gym, the guided first run.",
    help: lines(
      "Each row says what the check does, what it costs, how long it takes and what it writes; doctor, catalog and hello are ticked.",
      "Run the ticked checks runs them in order as one job; each row shows its state and its lines as they come.",
      "The gym runs local models only (it lists the models it would run on); the guided first run shows its card first, then its box can be ticked.",
      "The same five as halo check in a terminal; the rail's Last check is the last run here.",
    ),
  },
  "setup-summary": {
    about: "What this setup holds now, one row per step, each with a Change jump to its page.",
    help: lines(
      "A ticked row has what it needs; a row still to do says what is missing.",
      "Run the ticked checks runs the checks ticked on the Check page; The Check page opens it to change the ticks or read each log.",
      "The guided first run's card says what halo start does, the models it calls, the estimate, the time and what it writes.",
    ),
  },
};
