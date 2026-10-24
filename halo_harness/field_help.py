"""halo_harness.field_help -- the one plain line per field of a bio and a lineup
(and, 3.2.0.0 R1, of a pack's pack.yaml: `PACK`)
(Halo 3.1.1.0 R3: "one editor of record"). The TUI's read-only views
(tui/dialogs/agent_bio_editor.py, tui/dialogs/lineup_editor.py) show these
lines under each field, and Studio's bio form and lineup inspector show the
same lines: Studio reads them from `GET /api/field-help`
(studio/field_help_api.py), the bundle carries no copy.

Keys are `section.key` (a bio's `models.preference`, a lineup section's
`delegation.mode`); a lineup section's own line is its meaning. A field with
no entry shows no line (its label says it all).
"""

from __future__ import annotations

#: The bio's identity fields (no section; they never inherit through `extends`).
IDENTITY = {
    "name": "how /agent calls and lineups name this bio",
    "description": "one line: what this agent is for",
    "kind": "which family it belongs to (main, subagent, researcher, judge, reviewer, custom, media)",
    "tags": "search labels, comma separated",
    "extends": "inherit every field of another bio; the fields set here win",
    "from_pack": "the pack and version this bio was cloned from (pack@1.0.0); it changes nothing at run time",
}

#: One line per bio field, `section.key`.
BIO = {
    "models.preference": "the model this agent runs on, when it runs",
    "models.fallback": "what to switch to when the preferred model keeps failing",
    "models.needs": "with preference auto: what the picked model must have (vision, audio, video, pdf, reasoning, tools, long-context)",
    "models.effort": "how hard the model thinks (higher = better, slower, pricier)",
    "models.thinking": "let the model's own native thinking blocks through",
    "models.capabilities": "what the model must do (long-context, vision, tools ...): the best catalog model with every one; none: your default model",
    "models.context_budget": "cap this agent's context at a fraction (0-1) of the model's window",
    "tools.allow": "the only tools this agent may call (blank = the default set)",
    "tools.deny": "tools to withhold from this agent, even when allowed elsewhere",
    "tools.mcp_servers": "which MCP servers' tools this agent may call",
    "tools.permission_mode": "how permission asks are decided for this agent's tool calls",
    "tools.needs": "a pack bio's grants (bash, network, home-write, mcp:<server>): halo pack enable <id> --grant <need>",
    "tools.rules": "extra allow/ask/deny rules, one per line, the settings.json grammar (deny Bash(git push*))",
    "context.files": "files put in front of this agent's prompt (its reading list)",
    "context.skills": "skills this agent may invoke",
    "context.memory": "a private memory namespace (blank = no auto-memory)",
    "context.prompt_notes": "lines added after the bio's prompt (a coach card's Apply fills this)",
    "limits.max_iterations": "stop after this many model turns (0 = no cap)",
    "limits.timeout": "stop the whole run after this long (20m, 2h, 90s, 1d)",
    "limits.max_budget_usd": "stop when this agent's own spend passes this",
    "limits.concurrency": "how many copies may run at once",
    "output.handoff": "how the result returns: a summary, the full text, or structured",
    "output.report_to": "which position its results go back to",
    "environment.worktree": "run in its own git worktree (isolated edits)",
    "environment.offline": "never touch the network",
    "acceptance.prompt": "the one-line smoke prompt `halo doctor --agents` runs",
    "acceptance.expect": "what a passing answer looks like (a substring, or non-empty)",
    "schedule.cron": "a 5-field cron expression; set this or every, not both",
    "schedule.every": "a period like 30m, 1h30m or 45s; set this or cron, not both",
    "schedule.prompt": "what the agent is asked each time the schedule fires",
    "schedule.model": "a model for the scheduled runs only (blank: the bio's own)",
    "triggers": "start this agent on a file change, a halo event or a message (from a role), once each time",
    "hooks": "commands run before or after a tool call, at the start or the finish (edit as YAML)",
}

#: One line per lineup section: what it is for.
LINEUP_SECTIONS = {
    "delegation": "how the main agent hands work to the others (mode, how many at once, the hand-back shape)",
    "routing": "which role or alias a kind of task goes to",
    "budget": "when delegation stops: money, turns, time, for the whole lineup",
    "escalation": "when a stuck member switches to a bigger model",
    "context": "the files, skills and memory every member starts with",
    "permissions": "the lineup's own permission mode and rules, on top of each bio's own",
    "pipeline": "stages that run in order; a required gate must pass",
    "acceptance": "the one smoke prompt `halo doctor --teams` runs through this lineup, and the test and review an Orchestra run on it starts with",
    "tiers": "stacks of members: main alone in tier 0; each tier spawns only into the next one down; "
             "a tier may name its own model and a trigger that starts it",
}

#: One line per lineup section field, `section.path` (`section` alone: a section edited as one value).
LINEUP_FIELDS = {
    "delegation.mode": "manual, by-skill (routes by the words in a task) or round-robin",
    "delegation.max_parallel": "how many members may run at the same time",
    "delegation.max_depth": "1: only main spawns; a three-tier stack needs 2",
    "delegation.handoff": "how a member's result comes back: a summary, the full text, or structured",
    "delegation.forward_text": "show the member's text as it writes, not only at the end",
    "routing": "task kind -> member; default catches the rest",
    "budget.max_budget_usd": "stop delegating when the lineup's spend passes this",
    "budget.max_total_turns": "stop after this many turns across all members",
    "budget.max_wall_time": "stop after this long (3h, 45m, 1d)",
    "budget.agents_may_exceed": "a member may go past its own bio's budget",
    "budget.band": "an auto member's model pick: low the cheapest that fits, mid the best within 3x, high the strongest",
    "escalation.triggers": "what counts as stuck: tool failures, a context overflow, an exhausted budget",
    "escalation.to": "the model a stuck member switches to",
    "escalation.ask": "ask first (the approval card) before switching",
    "escalation.allow_fallbacks": "try the bio's own fallbacks before escalating",
    "context.files": "files every member reads",
    "context.skills": "skills every member may invoke",
    "context.memory.namespace": "the shared memory every member reads",
    "context.memory.writers": "the members that may write the shared memory",
    "permissions.mode": "the permission mode for every member's tool calls",
    "permissions.rules.deny": "rules every member is held to: these tool calls never run",
    "permissions.rules.ask": "these tool calls ask first",
    "permissions.rules.allow": "these tool calls run without asking",
    "permissions.offline": "no network tools for any member",
    "pipeline.stages": "one row per stage, in order: its name, the role or alias that runs it, its gate",
    "acceptance.prompt": "the smoke prompt",
    "acceptance.expect": "what a passing answer looks like (a substring, or non-empty)",
    "acceptance.test": "the test command an Orchestra run on this lineup starts with (halo orchestra new --lineup)",
    "acceptance.review": "an Orchestra run on this lineup pauses for the plan's review before it runs",
    "tiers": "tier 0 holds main alone; members left out join the last tier",
    # 3.1.6.0 R1: the Roles canvas's tier controls (Add tier, the box head, the box menu)
    "tiers.add": "a new tier box: name it, Enter adds it, then drag cards in (the first one also puts main alone in tier 0)",
    "tiers.rename": "double-click the name to rename the tier; Enter keeps it, Escape drops it",
    "tiers.menu": "this tier's own menu: rename, model, trigger, max parallel, delete",
    "tiers.model": "what this tier's members run on, unless a card names its own model or its bio pins one",
    "tiers.trigger": "starts this tier's lead (its first card) with the prompt, while a session on this lineup runs; "
                     "the lead may spawn its own tier and the next",
    "tiers.max_parallel": "how many of this tier's members may run at once (blank: no cap)",
    "tiers.delete": "remove the tier; its cards fall to the last tier (tier 0 stays)",
}

#: One line per field of a lineup's assignment (a card on the Roles canvas).
ASSIGNMENT = {
    "role": "which job this row picks the model for (main, subagent, reviewer ...)",
    "agent": "the bio that runs that job; a price shows in the costs",
    "as": "the name routing, tiers, positions and bios call this row by",
    "instances": "how many copies may run at once",
    "use_for": "words in a task that route it here, comma separated",
    "models": "a model for this row only (blank: the bio's own)",
    "description": "one line: what this lineup is for",
    "about": "how the pieces work together; members read it as 'How this team works'",
    "extends": "another lineup to inherit sections from",
    "workflows": "the pack workflows this lineup runs (a pack's lineup names its pack's own)",
    "from_pack": "the pack and version this lineup was cloned from (pack@1.0.0); it changes nothing at run time",
}

#: 3.1.4.0 R4: the one model control (Studio's ModelSelect) wherever an agent is configured.
MODEL_SELECT = {
    "runs_on": "the model this card runs on today: its own model, else its bio's",
    "card": "a model for this card only; the first option keeps the bio's own",
    "main": "the lineup's main card: a session on this lineup starts on it",
    "bio": "the model every card on this bio runs on, unless the card names its own",
    "orchestra": "the model the lead and the workers run on; the first option keeps the lineup's roles",
    "design": "the model this project's turns run on; the first option keeps the default model",
    "team": "a stage runs on its lead member's lineup card: change the model there",
    "more": "the whole catalog as a table: search, sort by price or context, or type a ref",
    "test": "a one-token round trip through the same path a session uses",
    "refresh": "pull every enabled provider's model list again",
}


#: 3.2.0.0 R1: one line per key of a pack's pack.yaml (docs/EXTENSION_API.md "The manifest").
PACK = {
    "id": "the pack's id and namespace: its folder, and the prefix of every name it offers (doc-review)",
    "name": "the name a person reads",
    "version": "the pack's own version, semver (1.2.0)",
    "description": "one line: what the pack adds",
    "author": "who maintains it (a name, or name, email and url)",
    "license": "its license, an SPDX id such as MIT",
    "halo_api": "the extension API versions it works with ({min: '1.0', max: '1.9'})",
    "halo": "the Halo versions it works with (halo --version)",
    "capabilities": "what it can do, as names (docs.review)",
    "requires": "other packs it needs, each with a version or a range",
    "contributes.agents": "its bios (agents/<name>.yaml, listed as <id>--<name>) and plugin agents (agents/<name>.md)",
    "contributes.teams": "its lineups (teams/<name>.yaml, listed as <id>--<name>)",
    "contributes.skills": "its skills folder (skills), each skill named <id>:<skill>",
    "contributes.commands": "its commands folder (commands), each command named <id>:<command>",
    "contributes.hooks": "its hooks file (hooks/hooks.json); loads once you grant hooks",
    "contributes.mcp": "its MCP servers (from .mcp.json); each starts once you grant mcp:<server>",
    "contributes.studio": "what it adds to Studio: sections after Orchestra, panels, palette lines, a settings form, its event lines and attention rows",
    "contributes.fleet": "what it brings to the fleet: worker capabilities (each with what it requires of a host), mission inspector lines, mission metadata",
    "contributes.artifacts": "its artifact schemas (artifacts/<name>.json): a workflow output's type, drawn by its x-halo-view",
    "contributes.events": "the event kinds it publishes on Studio's live feed; a kind's schema is events/<kind>.json",
    "contributes.workflows": "its workflows (workflows/<name>.yaml), compiled to Orchestra runs: halo workflow run <id>/<name>",
    "config.schema": "the shape of its settings (packs.settings.<id> in config.json)",
    "config.defaults": "the settings it starts with; yours win",
    "permissions": "what it asks you to grant: mcp:<server>, hooks, bash, network, home-write, studio-script",
    "migrations": "what changes for you between two versions; halo pack update prints it",
}


def as_json() -> dict:
    """What `GET /api/field-help` answers."""
    return {"identity": dict(IDENTITY), "bio": dict(BIO), "lineup_sections": dict(LINEUP_SECTIONS),
            "lineup_fields": dict(LINEUP_FIELDS), "assignment": dict(ASSIGNMENT), "model_select": dict(MODEL_SELECT),
            "pack": dict(PACK)}


def bio_line(section: str, key: str = "") -> str:
    """The line for a bio field (`bio_line("models", "preference")`), or ''."""
    if not key:
        return IDENTITY.get(section) or BIO.get(section) or ""
    return BIO.get(f"{section}.{key}", "")


def lineup_line(section: str, path: str = "") -> str:
    """The line for a lineup section (no path: its meaning) or one of its fields, or ''."""
    if not path:
        return LINEUP_SECTIONS.get(section, "")
    return LINEUP_FIELDS.get(f"{section}.{path}", "")
