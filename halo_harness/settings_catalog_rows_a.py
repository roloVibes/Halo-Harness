"""halo_harness.settings_catalog_rows_a -- the Settings rows of General, Agents and roles, Coach and improve,
Knowledge and recall, Supervise, Steer and turn and Models (settings_catalog.py has the shape; one row per line:
key, group, title, kind, default, choices, help, effect, secret)."""

from __future__ import annotations

from halo_harness.settings_catalog import Row
from halo_harness.theme import _BASE_THEMES, _SUFFIXES

_THEMES = tuple(f"{base}{suffix}" for base in _BASE_THEMES for suffix in _SUFFIXES)  # theme.VALID_THEMES in the wizard's order
_MODES = ("auto", "acceptEdits", "default", "plan")
_EFFORTS = ("low", "medium", "high", "xhigh", "max")

ROWS = [
    Row("model", "general", "Default model", "model", None, (), "The model a new session starts on; unset, the built-in default applies.", "next session"),
    Row("team", "general", "Active lineup", "string", None, (), "The lineup a session runs; unset, the shipped auto lineup runs.", "next session"),
    Row("permission_mode", "general", "Permission mode", "enum", None, _MODES, "The permission mode new sessions start in; auto allows everything except your own deny and ask rules.", "next session"),
    Row("effort", "general", "Effort", "enum", None, _EFFORTS, "The reasoning effort a session starts with when no flag and no last-used effort says otherwise.", "next session"),
    Row("model_memory", "general", "Model memory", "enum", "cwd", ("cwd", "global"), "Whether the last-used model and effort are remembered per folder (cwd) or once for every folder (global).", "next session"),
    Row("theme", "general", "Terminal theme", "enum", None, _THEMES, "The colours of halo in your terminal; unset, picked from the terminal's truecolor support.", "next launch"),
    Row("intro", "general", "Launch intro", "bool", True, (), "Play the launch intro; --no-intro skips it for one run.", "next launch"),
    Row("tips", "general", "Tips", "bool", True, (), "Rotating tips in the input line; off leaves the line plain.", "next launch"),
    Row("images", "general", "Images", "enum", "inline", ("inline", "caption"), "Draw images inline in the terminal, or show a caption line; --no-inline-images overrides it for one run.", "next launch"),
    Row("quit_on_double_ctrl_c", "general", "Quit on a second Ctrl+C", "bool", True, (), "A second Ctrl+C within 3 s opens the Quit Halo? card; off, every Ctrl+C just copies.", "now"),
    Row("clipboard.crlf", "general", "Copy with CRLF", "bool", False, (), "A copy uses CRLF line endings instead of LF.", "now"),
    Row("mcpPreload", "general", "MCP preload", "list", None, (), "Wire tool names to preload whatever the catalog's own alwaysLoad rule says.", "next session"),
    Row("compactionModel", "general", "Compaction model", "model", None, (), "The model that writes a compaction's summary; unset, the session model (billed at its own rates).", "now"),
    Row("agents.max_concurrent", "agents", "Agents at once", "int", 4, (), "How many sub-agents may run at the same time.", "next session"),
    Row("agents.max_depth", "agents", "Agent depth", "int", 1, (), "How deep sub-agents may spawn sub-agents of their own (1 to 3).", "next session"),
    Row("roles.enabled", "agents", "Roles on", "bool", True, (), "Sessions route work by role (planner, coder, reviewer ...); off, one model does everything.", "next session"),
    Row("roles.editor", "agents", "Roles editor", "enum", None, ("external",), "external opens /roles edit in your $EDITOR instead of the form.", "now"),
    Row("roles.<role>", "agents", "Role model", "keyed", None, (), "The model one role runs on (a model ref, or a mapping with model and effort); the lineup's own wins over it.", "next session"),
    Row("improve.enabled", "coach", "Improve on", "bool", True, (), "The /improve suggestions read your sessions and offer changes.", "now"),
    Row("improve.hint", "coach", "Improve hint", "bool", True, (), "Show a one-line hint when a session crosses one of the hint thresholds.", "next session"),
    Row("improve.model", "coach", "Improve model", "model", None, (), "The model /improve drafts with; unset, the small model, then the session model.", "now"),
    Row("improve.since_days", "coach", "Improve window", "int", 7, (), "How many days of sessions /improve reads.", "now"),
    Row("improve.max_candidates", "coach", "Improve candidates", "int", 8, (), "How many candidates /improve offers at most (hard-capped at 8).", "now"),
    Row("improve.hint_threshold.repairs", "coach", "Hint after repairs", "int", 3, (), "Repairs in a session before the improve hint shows.", "next session"),
    Row("improve.hint_threshold.edit_failures", "coach", "Hint after failed edits", "int", 2, (), "Failed edits in a session before the improve hint shows.", "next session"),
    Row("improve.hint_threshold.loop_breaker", "coach", "Hint after loop breaks", "int", 1, (), "Loop-breaker stops in a session before the improve hint shows.", "next session"),
    Row("coach.probe.k", "coach", "Probe pairs", "int", 1, (), "How many pairs of candidate overlays a coach probe drafts and runs when no --k is given (at most 4).", "now"),
    Row("coach.probe.budget_factor", "coach", "Probe budget factor", "float", 1.5, (), "Each probe run may spend the reference run's cost times this.", "now"),
    Row("coach.library.cite", "coach", "Cite the library", "bool", True, (), "The coach cites the improvement library entries earlier Applies left for runs like this one.", "now"),
    Row("knowledge.write", "knowledge", "Write knowledge", "bool", True, (), "The judge, the gate, the coach's Apply and the supervisor write findings and decisions to the knowledge store.", "now"),
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
    Row("models.roster", "models", "Model roster", "bool", True, (), "The main session reads the model roster (what each model is good at) at its start.", "next session"),
    Row("models.learn", "models", "Auto learns", "bool", True, (), "The auto pick weighs what was measured per task kind and the roster drops a model that keeps failing one.", "now"),
    Row("models.learn.min_tasks", "models", "Learn after tasks", "int", 3, (), "Checked tasks of a kind a model needs before its rate counts.", "now"),
    Row("models.learn.window_days", "models", "Learn window (days)", "int", 30, (), "Only outcome rows of the last N days count; 0 counts every row.", "now"),
    Row("models.learn.drop_below", "models", "Drop below", "float", 0.34, (), "A model whose rate for a kind is below this is dropped for the kind; 0 drops nothing.", "now"),
    Row("prompt.lean", "models", "Lean prompt", "enum", "auto", ("auto", "on", "off"), "What Halo sends a small model: the topic index as one line per file, the memory capped, the tools capped by the window; auto is a local model or a window under 64k.", "now"),
    Row("prompt.topics_max", "models", "Topic files sent", "int", 12, (), "Under the lean prompt, the newest topic files named in the memory block; the rest are one line (/memory topics lists them).", "now"),
    Row("prompt.memory_max_tokens", "models", "Memory tokens at most", "int", 4000, (), "Under the lean prompt, MEMORY.md is held to this many tokens, the newest entries kept and the cut said in one line.", "now"),
    Row("prompt.preflight", "models", "Over the window", "enum", "ask", ("ask", "compact", "send"), "A local request larger than its window: ask (compact, a bigger-window model or send anyway; compact when nobody can answer), compact, or send it to be cut.", "now"),
    Row("models.think.<ref>", "models", "Think on a local model", "keyed", None, ("on", "off", "default"), "Per local model ref: on or off sends Ollama's think field whatever the effort level, default sends none (the model's own); gpt-oss also takes low, medium and high; unset, the effort level decides.", "now"),
]
