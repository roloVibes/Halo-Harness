"""halo_harness.settings_catalog_rows_a -- the Settings rows of General, Agents and roles,
Knowledge and recall, Supervise, Steer and turn and Models (settings_catalog.py has the shape; one row per line:
key, group, title, kind, default, choices, help, effect, secret)."""

from __future__ import annotations

from halo_harness.settings_catalog import Row
from halo_harness.themes.registry import LIVE_VALUES

_THEMES = LIVE_VALUES  # 3.3.12.0 R1: the palette registry's names (each id, then -daltonized, -ansi); R2: read at each use; 3.3.15.0 R4: "auto" first
_MODES = ("auto", "acceptEdits", "default", "plan")
_EFFORTS = ("low", "medium", "high", "xhigh", "max")

ROWS = [
    Row("model", "general", "Default model", "model", None, (), "The model a new session starts on; unset, the built-in default applies.", "next session"),
    Row("team", "general", "Active lineup", "string", None, (), "The lineup a session runs; unset, the shipped auto lineup runs.", "next session"),
    Row("permission_mode", "general", "Permission mode", "enum", None, _MODES, "The permission mode new sessions start in; auto allows everything except your own deny and ask rules.", "next session"),
    Row("effort", "general", "Effort", "enum", None, _EFFORTS, "The reasoning effort a session starts with when no flag and no last-used effort says otherwise.", "next session"),
    Row("model_memory", "general", "Model memory", "enum", "cwd", ("cwd", "global"), "Whether the last-used model and effort are remembered per folder (cwd) or once for every folder (global).", "next session"),
    Row("tools.show_halo_secrets", "general", "Show Halo's own secret files", "bool", False, (), "Off: the secret values in Halo's own files (the Studio token file, provider keys, sign-ins) read as [hidden] in what Read, Grep and Bash show, with one line saying so; on shows them (tools/halo_secrets.py).", "now"),
    Row("theme", "general", "Theme", "enum", None, _THEMES, "One palette for the terminal and Studio (the Themes page shows them all); Studio redraws at once, a running terminal on /theme. Unset: instrument everywhere (instrument-ansi in a terminal without truecolor); auto: Studio follows the system (instrument on dark, paper on light).", "next launch"),
    Row("intro", "general", "Launch intro", "bool", True, (), "Play the launch intro; --no-intro skips it for one run.", "next launch"),
    Row("tips", "general", "Tips", "bool", True, (), "Rotating tips in the input line; off leaves the line plain.", "next launch"),
    Row("images", "general", "Images", "enum", "inline", ("inline", "caption"), "Draw images inline in the terminal, or show a caption line; --no-inline-images overrides it for one run.", "next launch"),
    Row("quit_on_double_ctrl_c", "general", "Quit on a second Ctrl+C", "bool", True, (), "A second Ctrl+C within 3 s opens the Quit Halo? card; off, every Ctrl+C just copies.", "now"),
    Row("clipboard.crlf", "general", "Copy with CRLF", "bool", False, (), "A copy uses CRLF line endings instead of LF.", "now"),
    Row("mcpPreload", "general", "MCP preload", "list", None, (), "Wire tool names to preload whatever the catalog's own alwaysLoad rule says.", "next session"),
    Row("compactionModel", "general", "Compaction model", "model", None, (), "The model that writes a compaction's summary; unset, the session model (billed at its own rates).", "now"),
    Row("studio.hover_cards", "studio", "Hover cards", "bool", True, (), "Resting the pointer on a box in Agents (a Cast card, an agent, a session, a machine, a lane, a square) or focusing it with the keyboard shows a card of what it is and does; off, the boxes show their plain tooltips.", "now"),
    Row("studio.alerts", "studio", "Alerts", "enum", "none", ("none", "browser"), "When something starts waiting on you (a permission, a question, a plan, a gate), one alert by this channel: none, or browser (the notification of a browser that allowed it: Settings -> Studio -> Alerts asks it on your click; a click on it opens the ask).", "now"),
    Row("agents.max_concurrent", "agents", "Agents at once", "int", 4, (), "How many sub-agents may run at the same time.", "next session"),
    Row("agents.max_depth", "agents", "Agent depth", "int", 1, (), "How deep sub-agents may spawn sub-agents of their own (1 to 3).", "next session"),
    Row("workflows.enabled", "agents", "Workflow squares", "list", ["media"], (), "The squares the auto lineup may hand work to (the Workflow tool); another lineup lists its own under workflows:.", "next session"),
    Row("workflows.when.<square>", "agents", "When main uses a square", "keyed", {}, (), "On the auto lineup, one square's rule for when main hands it work: needs (pdf, vision, audio, video, code, plan, research, review, work-data), words, mode (auto, named, always, off); unset, its covers.", "next session"),
    Row("roles.enabled", "agents", "Roles on", "bool", True, (), "Sessions route work by role (planner, coder, reviewer ...); off, one model does everything.", "next session"),
    Row("roles.editor", "agents", "Roles editor", "enum", None, ("external",), "external opens /roles edit in your $EDITOR instead of the form.", "now"),
    Row("roles.<role>", "agents", "Role model", "keyed", None, (), "The model one role runs on (a model ref, or a mapping with model and effort); the lineup's own wins over it.", "next session"),
    Row("knowledge.write", "knowledge", "Write knowledge", "bool", True, (), "The judge, the gate, the coach's Apply and the supervisor write findings and decisions to the knowledge store.", "now"),
    Row("knowledge.gate_keep", "knowledge", "Passed-gate records kept", "int", 50, (), "How many passed-gate records each project keeps, the newest; an older one is forgotten when a new one is written (halo knowledge prune removes more).", "now"),
    Row("knowledge.brief", "knowledge", "Knowledge in briefs", "bool", True, (), "An Orchestra worker's brief carries up to three findings and decisions recall ranks for its job.", "now"),
    Row("recall.sources", "knowledge", "Recall sources", "list", [], (), "Folders of your own Markdown notes recall reads in place (an Obsidian vault is one).", "now"),
    Row("supervise.tick_s", "supervise", "Tick", "int", 5, (), "Seconds between two ticks of the supervisor.", "next launch"),
    Row("supervise.max_running", "supervise", "Goals at once", "int", 1, (), "How many goals the supervisor runs at once.", "now"),
    Row("supervise.replan", "supervise", "Replan", "enum", "none", ("none", "auto", "review"), "What the supervisor does with a run that drifts: stop only, replan, or park it for review.", "now"),
    Row("supervise.replan_forecast", "supervise", "Forecast drift", "float", 1.25, (), "A run drifts when its spend plus the lanes left pass the cap times this.", "now"),
    Row("supervise.replan_returns", "supervise", "Returns drift", "int", 2, (), "A run drifts when a lane is sent back this many times.", "now"),
    Row("supervise.replan_block_s", "supervise", "Blocked drift", "int", 600, (), "Seconds a lane may wait on a hand-off or a refused claim before the run drifts.", "now"),
    Row("supervise.replan_stall_s", "supervise", "Stalled drift", "int", 900, (), "Seconds a writing lane may log no event before the run drifts.", "now"),
    Row("supervise.replan_cooldown_s", "supervise", "Replan cooldown", "int", 300, (), "Seconds after a goal's last replan before it may replan again.", "now"),
    Row("supervise.replan_max", "supervise", "Replans per goal", "int", 2, (), "Replans per goal; past it a drift is left to the stops.", "now"),
    Row("supervise.asks", "supervise", "Asks", "enum", "park", ("park", "deny"), "A supervised job goal's permission card or question: park it in Attention, or deny it at once.", "now"),
    Row("supervise.budget_usd", "supervise", "Queue budget (USD)", "float", None, (), "The whole queue's spend cap; a lane that would pass it does not start.", "now"),
    Row("supervise.retries", "supervise", "Retries", "int", 1, (), "How many times a crashed goal is retried from its checkpoint before it parks.", "now"),
    Row("supervise.max_minutes", "supervise", "Time limit (minutes)", "int", 0, (), "A goal's time limit; 0 is none.", "now"),
    Row("steer.restart_when_silent", "steer", "Restart a silent call", "bool", True, (), "A steer typed while a model call has sent nothing yet aborts that call and resends it with the steer.", "now"),
    Row("steer.silent_restart_s", "steer", "Silent call resend (s)", "int", 60, (), "A model call with no first token after this many seconds is resent once; 0 turns it off.", "now"),
    Row("turn.nudge_promises", "steer", "Nudge a promise", "bool", True, (), "A reply that promises more work and calls no tool gets one notice and one more model call.", "now"),
    Row("background.when_done", "steer", "When background work finishes", "enum", "continue", ("continue", "tell", "wait"), "A background sub-agent or job that finishes while the session is idle: continue (shown at once, then the agent takes a turn by itself to read the results and report or carry on), tell (shown at once only; your next message reads it), or wait for my next message (nothing until then).", "now"),
    Row("background.self_turns", "steer", "Turns by itself in a row", "int", 3, (), "How many turns finished background work may start in a row with no message from you; past it, or at the session's spend cap, one line says so and Halo waits for you.", "now"),
    Row("models.roster", "models", "Model roster", "bool", True, (), "The main session reads the model roster (what each model is good at) at its start.", "next session"),
    Row("models.learn", "models", "Auto learns", "bool", True, (), "The auto pick weighs what was measured per task kind and the roster drops a model that keeps failing one.", "now"),
    Row("models.learn.min_tasks", "models", "Learn after tasks", "int", 3, (), "Checked tasks of a kind a model needs before its rate counts.", "now"),
    Row("models.learn.window_days", "models", "Learn window (days)", "int", 30, (), "Only outcome rows of the last N days count; 0 counts every row.", "now"),
    Row("models.learn.drop_below", "models", "Drop below", "float", 0.34, (), "A model whose rate for a kind is below this is dropped for the kind; 0 drops nothing.", "now"),
    Row("prompt.lean", "models", "Lean prompt", "enum", "auto", ("auto", "on", "off"), "What Halo sends a small model: the topic index as one line per file, the memory capped, the tools capped by the window; auto is a local model or a window under 64k.", "now"),
    Row("prompt.topics_max", "models", "Topic files sent", "int", 12, (), "Under the lean prompt, the newest topic files named in the memory block; the rest are one line (/memory topics lists them).", "now"),
    Row("prompt.memory_max_tokens", "models", "Memory tokens at most", "int", 4000, (), "Under the lean prompt, MEMORY.md is held to this many tokens, the newest entries kept and the cut said in one line.", "now"),
    Row("prompt.preflight", "models", "Over the window", "enum", "ask", ("ask", "compact", "send"), "A local request larger than its window: ask (compact, a bigger-window model or send anyway; compact when nobody can answer), compact, or send it to be cut.", "now"),
    Row("prompt.shell", "models", "Lean shell (Windows)", "enum", "auto", ("auto", "bash", "powershell"), "Under the lean prompt on Windows, the one shell tool offered: auto is Bash when Git Bash is found, else PowerShell; the other stays callable by name and through ToolSearch.", "now"),
    Row("models.think.<ref>", "models", "Think on a local model", "keyed", None, ("on", "off", "default"), "Per local model ref: on or off sends Ollama's think field whatever the effort level, default sends none (the model's own); gpt-oss also takes low, medium and high; unset, the effort level decides.", "now"),
]
