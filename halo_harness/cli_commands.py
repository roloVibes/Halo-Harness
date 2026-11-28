"""halo_harness.cli_commands -- every top-level `halo <command>` (Halo 3.6.0.0 R16): the one place a command is
registered. cli.py's dispatcher runs a command from here, and `halo --help` lists it from here, grouped (the everyday
ones first, then by area), each with its one-line purpose. A new command is one row below; it then runs and shows in
`halo --help` by itself (tests/test_cli_commands.py checks both directions).

`kind`: "" = listed in `halo --help`; "internal" = a helper Halo starts or offers for itself, left out of the help
on purpose; "retired" = a verb that left, which only says where to go (cli.py's GONE_VERBS and `design`), left out too.

Data only, nothing imported: building `halo --help` loads no command's module, so it stays fast.
"""
from __future__ import annotations

EVERYDAY = "Everyday"
AGENTS = "Agents and workflows"
MODELS = "Models and providers"
RECORDS = "Sessions and records"
SETUP = "Setup, settings and tools"
GROUPS = (EVERYDAY, AGENTS, MODELS, RECORDS, SETUP)


class Command:
    __slots__ = ("name", "target", "group", "purpose", "kind")

    def __init__(self, name: str, target: str, group: str, purpose: str, kind: str = "") -> None:
        self.name, self.target, self.group, self.purpose, self.kind = name, target, group, purpose, kind

    def __repr__(self) -> str:
        return f"Command({self.name!r}, {self.target!r}, kind={self.kind!r})"


def _c(name: str, target: str, group: str, purpose: str, kind: str = "") -> Command:
    return Command(name, target, group, purpose, kind)


#: name, "module:function" (called with the rest of argv), group, purpose, kind
COMMANDS = (
    _c("init", "halo_harness.init_cli:cmd_init", EVERYDAY, "set up a fresh box (opens Studio's Setup)"),
    _c("studio", "halo_harness.studio:cmd_studio", EVERYDAY, "the GUI: your sessions, agents, workflows, maps and models"),
    _c("doctor", "halo_harness.doctor:cmd_doctor", EVERYDAY, "check this install, its providers and tools"),
    _c("check", "halo_harness.check_cli:cmd_check", EVERYDAY, "the checks Halo offers after setup"),
    _c("update", "halo_harness.update_cli:cmd_update", EVERYDAY, "update Halo, or see whether there is an update"),
    _c("whatsnew", "halo_harness.whatsnew_cli:cmd_whatsnew", EVERYDAY, "what a version changed"),
    _c("explain", "halo_harness.explain_cli:cmd_explain", EVERYDAY, "one paragraph per word Halo uses"),
    _c("settings", "halo_harness.settings_cli:cmd_settings", EVERYDAY, "every config key, in Studio's Settings"),
    _c("setup", "halo_harness.setup_cli:cmd_setup", EVERYDAY, "open one page of Studio's Setup"),

    _c("agents", "halo_harness.agents_cli:cmd_agents", AGENTS, "your agents: list, show, new, edit, try"),
    _c("workflows", "halo_harness.workflows_cli:cmd_workflows", AGENTS, "your workflows: list, show, new, edit, try, run"),
    _c("maps", "halo_harness.maps_cli:cmd_maps", AGENTS, "your maps, the one your sessions run on: list, show, use, edit"),
    _c("orchestra", "halo_harness.orchestra_cli:cmd_orchestra", AGENTS, "the Orchestra: a goal, its steps, claims, the run log"),
    _c("work", "halo_harness.work_cli:cmd_work", AGENTS, "the units of any run, as one table"),
    _c("supervise", "halo_harness.supervise.cli:cmd_supervise", AGENTS, "the supervisor: works the goal queue with no terminal"),
    _c("goal", "halo_harness.supervise.goal_cli:cmd_goal", AGENTS, "the supervisor's goal queue: add, list, show, hold, cancel"),
    _c("review", "halo_harness.review.cli:cmd_review", AGENTS, "review a change and rank what would break"),
    _c("outcomes", "halo_harness.outcomes.cli:cmd_outcomes", AGENTS, "every agent task's outcome"),
    _c("knowledge", "halo_harness.knowledge.cli:cmd_knowledge", AGENTS, "the findings and decisions agents keep"),
    _c("bg", "halo_harness.bg_cli:cmd_bg", AGENTS, "background runs: list, logs, stop, rm"),
    _c("ps", "halo_harness.ps_cli:cmd_ps", AGENTS,
       "every live process of Halo on this machine, and who owns it; --forget a record it cannot prove"),
    _c("stop", "halo_harness.ps_cli:cmd_stop", AGENTS, "stop a process of Halo, the orphans, or all of them"),
    _c("remote", "halo_harness.remote.cli:cmd_remote", AGENTS, "live sessions: list them, their agents, steer, stop"),
    _c("worktree", "halo_harness.worktree_cli:cmd_worktree", AGENTS, "remove a worktree a session made"),
    _c("isolation", "halo_harness.isolation.cli:cmd_isolation", AGENTS, "opt-in isolation for workers: the image, build, check"),
    _c("secrets", "halo_harness.isolation.secrets:cmd_secrets", AGENTS, "the secret broker: check each ref, names only"),

    _c("models", "halo_harness.catalog_cli:cmd_models", MODELS, "the models you can use, with context and price"),
    _c("providers", "halo_harness.providers_cli:cmd_providers", MODELS, "each provider: set up or not, reachable, models"),
    _c("local", "halo_harness.local_cli:cmd_local", MODELS, "local models, on this machine or another: ps, warm, unload, pull, measure"),
    _c("ollama", "halo_harness.ollama_cli:cmd_ollama", MODELS, "Ollama: the panel, discover, calibrate, tune, doctor"),
    _c("pool", "halo_harness.pool_cli:cmd_pool", MODELS, "the pool of machines that serve models: members, fit, advice"),
    _c("host", "halo_harness.host_cli:cmd_host", MODELS, "the model-free monitor a machine that serves models runs"),
    _c("copilot", "halo_harness.copilot_cli:cmd_copilot", MODELS, "your work's Copilot: sign in, status, ask"),
    _c("voice", "halo_harness.voice_cli:cmd_voice", MODELS, "speech models: the catalog, download, remove, serve"),
    _c("media", "halo_harness.media.cli:cmd_media", MODELS, "ComfyUI: init, doctor, serve, inspect, models, workflows"),
    _c("balances", "halo_harness.balances_cli:cmd_balances", MODELS, "what each provider account has left"),
    _c("gov", "halo_harness.gov_cli:cmd_gov", MODELS, "the gateway governor: each rate bucket, a host's recent calls"),
    _c("rules", "halo_harness.rules_cli:cmd_rules", MODELS, "the parameter rules Halo learned from provider rejections"),
    _c("gym", "halo_harness.gym_cli:cmd_gym", MODELS, "measure models at each kind of task"),
    _c("work-matrix", "halo_harness.work_matrix:cmd_work_matrix", MODELS, "one short call through every work endpoint"),

    _c("session", "halo_harness.session_trace_cli:cmd_session", RECORDS, "the session export: a session as one Markdown file"),
    _c("export", "halo_harness.export_cli:cmd_export", RECORDS, "the raw session log, JSON lines, for a script"),
    _c("stats", "halo_harness.stats_cli:cmd_stats", RECORDS, "tokens, cost and tools across sessions"),
    _c("report", "halo_harness.report_cli:cmd_report", RECORDS, "a finished run's report card"),
    _c("timeline", "halo_harness.bugreport_timeline_cli:cmd_timeline", RECORDS, "the timing of the last turns"),
    _c("recall", "halo_harness.recall:cmd_recall", RECORDS, "search memory and past sessions"),
    _c("bugreport", "halo_harness.bugreport:cmd_bugreport", RECORDS, "one paste with what a bug report needs"),
    _c("audit", "halo_harness.audit_cli:cmd_audit", RECORDS, "scan the tree or its history for private data"),

    _c("config", "halo_harness.config_cli:cmd_config", SETUP, "read and write Halo's config.json"),
    _c("pack", "halo_harness.packs.cli:cmd_pack", SETUP, "capability packs: list, install, enable, update, remove"),
    _c("mcp", "halo_harness.mcp_cli:cmd_mcp", SETUP, "MCP servers: list, get, add, remove"),
    _c("guest", "halo_harness.guest.install:cmd_guest", SETUP,
       "a Claude Code session in Studio, watch only: install, uninstall, status"),
    _c("preflight", "halo_harness.preflight:cmd_preflight", SETUP, "verify the tools before a long autonomous run"),
    _c("completion", "halo_harness.completion_cli:cmd_completion", SETUP, "a shell completion script: bash, zsh, PowerShell"),
    _c("proxy", "bridge:main", SETUP, "the local bridge that routes Claude Code's calls to other models"),

    # left out of `halo --help` on purpose
    _c("roles", "halo_harness.roles_cli:cmd_roles", AGENTS, "`roles point`: the write a steward or adviser line offers",
       kind="internal"),
    _c("teams", "", AGENTS, "lineups are gone (halo maps)", kind="retired"),
    _c("blocks", "", AGENTS, "blocks are workflows now (halo workflows)", kind="retired"),
    _c("workflow", "", AGENTS, "now halo workflows", kind="retired"),
    _c("design", "", SETUP, "Design is the design pack's", kind="retired"),
    _c("replay", "", RECORDS, "left Halo in 3.6.0.3 (halo session export)", kind="retired"),
)

# 3.6.0.3 B (Z12): the one line `halo replay`, `halo audit privacy --replays`, `halo report <an old file>` and Studio's
# live/report say; cli.py's own branch prints it to stderr and exits 2 (the verb never falls through to a prompt)
REPLAY_LEFT = ("halo replay (playing a session back, re-running a turn on another model) left Halo in 3.6.0.3. "
               "To keep a session as a file: halo session export <id>")

BY_NAME = {c.name: c for c in COMMANDS}


def listed() -> list:
    """The commands `halo --help` lists, in their order."""
    return [c for c in COMMANDS if not c.kind]


def help_text() -> str:
    """The commands block of `halo --help`: one heading per group, one line per command."""
    rows = listed()
    width = max(len(c.name) for c in rows) + 2
    out = ["Commands: `halo <command> --help` for each one's own."]
    for group in GROUPS:
        mine = [c for c in rows if c.group == group]
        if not mine:
            continue
        out.append(f"  {group}")
        out += [f"    {c.name.ljust(width)}{c.purpose}" for c in mine]
    out.append("  An enabled pack adds its own commands (coach, improve, start); `halo pack list` names them.")
    return "\n".join(out)
