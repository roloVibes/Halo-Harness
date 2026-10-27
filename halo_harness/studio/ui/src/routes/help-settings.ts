// What each Settings page holds (`about`, one line) and how to use it (`help`,
// a few short lines), 3.3.3.0 R2 (the Settings section, docs/STUDIO-sections.md
// "Settings"); routes/help.ts merges them into HELP. Each group page's head shows
// its `about` and, behind "How this page works", the shared lines and its own.
import type { Help } from "./help-orchestra";

const lines = (...l: string[]) => l.join("\n");

const EVERY = [
  "Each row is one config key of ~/.halo/config.json: its title, one help line, the control, and the halo config set line that does the same from a terminal.",
  "A change saves at once and the row says when it takes effect: now, in the next session, or on the next launch.",
  "A row marked default is not in config.json; Reset to default takes a key you set back out.",
  "The search box finds a row across every group; Mod+K lists every row as Settings: <title>.",
];

function page(about: string, ...own: string[]): Help {
  return { about, help: lines(...own, ...EVERY) };
}

export const SETTINGS_HELP: Record<string, Help> = {
  "settings-general": page("The model a session starts on, the lineup, the permission mode, effort, the terminal theme and the terminal's own switches.",
    "Setup sets the model, the permission mode, the theme and the lineup with a preview; here each is one row."),
  "settings-agents": page("How many sub-agents run at once and how deep, whether roles route the work, and the model each role runs on.",
    "A role's model is a table of the roles saved: change one, or add one in roles as JSON."),
  "settings-coach": page("The /improve suggestions and their hint, and the coach's probes and library citations."),
  "settings-knowledge": page("What the knowledge store records and briefs carry, and the folders of your own notes recall reads."),
  "settings-supervise": page("The supervisor's tick, how many goals it runs, when a run drifts and what it does then, and the queue's budget."),
  "settings-steer": page("What a steer does to a model call that has sent nothing yet, and the nudge after a reply that promises more work."),
  "settings-models": page("The model roster the main session reads, and how the auto pick learns from measured outcomes."),
  "settings-providers": page("Each provider on or off, and the knobs of Databricks, OpenAI, Experiential Labs and Hugging Face.",
    "Keys never live here: Setup's Providers page saves them to the env file."),
  "settings-ollama": page("The Ollama hosts, the per-host KV cache type and ssh GPU read, the tool cap, calibration and discovery.",
    "A host's own field (KV cache type, ssh) is a table of the hosts saved; add a host in ollama.hosts as JSON."),
  "settings-network": page("Offline (only local hosts are called) and the escalation that hands a local turn to a cloud model."),
  "settings-fleet": page("Whether sessions list themselves for Studio and a hub, what a hub sees and may do, the hub's port, the caps and missions."),
  "settings-remote": page("The Signal bridge's switches, its rate, how much it relays and its pairing code's life."),
  "settings-packs": page("Where halo pack install looks for packs, and each pack's own settings."),
  "settings-connectors": page("The claude.ai connectors: all of them on or off, discovery at start, and each connector's own switches."),
  "settings-worktree": page("What a -w session does with its own git worktree when it ends."),
  "settings-update": page("halo update's check, its daily note and the channel it follows."),
  "settings-local": page("Named local servers, the embeddings recall ranks with, the ComfyUI server and the governor that paces every call."),
};
