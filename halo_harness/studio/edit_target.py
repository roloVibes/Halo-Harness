"""halo_harness.studio.edit_target -- what `halo studio --edit` opens (Halo 3.1.1.0 R3; 3.6.0.0 R5: the three tabs).

Studio is the one editor of agents, workflows and maps. An edit target names what to open there:

    agent:<name>      Agents -> 1 · Agents, that agent's form
    workflow:<name>   Agents -> 2 · Workflows, that workflow's form
    map:<name>        Agents -> 3 · Map, that map

The old forms still parse and open the tab that replaced them, with the old files' one line (OLD_LINE): `bio:<name>`
(1 · Agents), `lineup:<name>[:<block>]` and `team` (3 · Map). It rides in the page URL as
`?mode=agents&view=<crew|workflows|map>&edit=<target>` (the token stays in the fragment):

    http://127.0.0.1:<port>/?mode=agents&view=crew&edit=agent:coder#t=<token>

`resolve` also takes a bare name (the TUI's `/edit coder`): an agent of that name, else a workflow, else a map.

3.3.0.0 R4: `setup`, `setup:first` and `setup:<block>` are Setup targets (studio/setup_door.py `SetupTarget`), the
doors `halo init`, `halo setup` and `/setup` open. 3.3.3.0 R2: `settings` and `settings:<group>` are Settings targets
(studio/settings_door.py); 3.3.5.0 R1: `local` and `local:<page>` are Local targets (studio/local_door.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

KINDS = ("agent", "workflow", "map")
OLD = ("bio", "lineup", "team")
USAGE = "agent:<name>, workflow:<name> or map:<name>"
OLD_LINE = "lineups and bios are no longer read: agents, workflows and maps live in ~/.halo/crew/"
VIEWS = {"agent": "crew", "bio": "crew", "workflow": "workflows", "map": "map", "lineup": "map", "team": "map"}
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class EditTarget:
    kind: str
    name: str = ""
    block: str = ""  # an old lineup target's page (read, not opened: lineups are gone)

    @property
    def mode(self) -> str:
        """The Studio section the target opens in."""
        return "agents"

    @property
    def view(self) -> str:
        """Agents' tab: 1 · Agents for an agent (or an old bio), 2 · Workflows, 3 · Map (a map, an old lineup or team)."""
        return VIEWS[self.kind]

    @property
    def old(self) -> bool:
        return self.kind in OLD

    @property
    def text(self) -> str:
        if self.kind == "team":
            return self.kind
        return f"{self.kind}:{self.name}" + (f":{self.block}" if self.block else "")

    def query(self) -> str:
        """`?mode=agents&view=crew&edit=agent:coder`: what goes in front of the URL's fragment."""
        return f"?mode={self.mode}&view={self.view}&edit={quote(self.text, safe=':')}"


def parse(text: str) -> "tuple[Optional[EditTarget], str]":
    """`(target, '')`, or `(None, why)` when `text` is not one of the targets above."""
    text = (text or "").strip()
    if text == "team":
        return EditTarget("team"), ""
    head = text.partition(":")[0].strip().lower()
    if head == "setup":  # 3.3.0.0 R4: Setup, its first run or one block (setup_door.py)
        from halo_harness.studio.setup_door import parse as parse_setup
        return parse_setup(text)
    if head == "settings":  # 3.3.3.0 R2: Settings, or one group's page (settings_door.py)
        from halo_harness.studio.settings_door import parse as parse_settings
        return parse_settings(text)
    if head == "local":  # 3.3.5.0 R1: Local, or one of its pages (local_door.py)
        from halo_harness.studio.local_door import parse as parse_local
        return parse_local(text)
    kind, sep, name = text.partition(":")
    kind, name = kind.strip().lower(), name.strip()
    if not sep or kind not in KINDS + ("bio", "lineup"):
        return None, f"{text!r} is not an edit target: use {USAGE}"
    name, _, block = name.partition(":") if kind == "lineup" else (name, "", "")
    name, block = name.strip(), block.strip().lower()
    if not _NAME.match(name):
        return None, f"{name!r} is not a valid {kind} name (letters, digits, - and _)"
    return EditTarget(kind, name, block), ""


def resolve(text: str, *, cwd=None, state_dir=None) -> "tuple[Optional[EditTarget], str]":
    """`parse`, plus a bare name: the agent of that name, else the workflow, else the map."""
    text = (text or "").strip()
    if not text:
        return None, f"name what to edit: {USAGE}"
    if ":" in text or text in ("team", "setup", "settings", "local"):
        return parse(text)
    from halo_harness.crew import store
    for kind in KINDS:
        if store.find(kind, text, cwd=cwd, state_dir=state_dir):
            return parse(f"{kind}:{text}")
    return None, f"no agent, workflow or map named {text!r}: use {USAGE}"
