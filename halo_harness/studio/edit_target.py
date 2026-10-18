"""halo_harness.studio.edit_target -- what `halo studio --edit` opens (Halo 3.1.1.0 R3).

Studio is the one editor of bios and lineups. An edit target names what to
open there:

    bio:<name>      Roles, the Bios panel open on that bio's form
    lineup:<name>   Roles, that lineup open with the Inspector on its Lineup tab
    team            Team, the Team section

It rides in the page URL as `?mode=<roles|team>&edit=<target>` (the token
stays in the fragment):

    http://127.0.0.1:<port>/?mode=roles&edit=bio:coder#t=<token>

`resolve` also takes a bare name (the TUI's `/edit coder`): a bio of that
name, else a lineup of that name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

KINDS = ("bio", "lineup", "team")
USAGE = "bio:<name>, lineup:<name> or team"


@dataclass(frozen=True)
class EditTarget:
    kind: str
    name: str = ""

    @property
    def mode(self) -> str:
        """The Studio section the target opens in."""
        return "team" if self.kind == "team" else "roles"

    @property
    def text(self) -> str:
        return self.kind if self.kind == "team" else f"{self.kind}:{self.name}"

    def query(self) -> str:
        """`?mode=roles&edit=bio:coder`: what goes in front of the URL's fragment."""
        return f"?mode={self.mode}&edit={quote(self.text, safe=':')}"


def _valid_name(kind: str, name: str) -> bool:
    if kind == "bio":
        from halo_harness.agents_yaml import is_valid_agent_name
        return is_valid_agent_name(name)
    from halo_harness.teams_yaml import is_valid_team_name
    return is_valid_team_name(name)


def parse(text: str) -> "tuple[Optional[EditTarget], str]":
    """`(target, '')`, or `(None, why)` when `text` is not `bio:<name>`, `lineup:<name>` or `team`."""
    text = (text or "").strip()
    if text == "team":
        return EditTarget("team"), ""
    kind, sep, name = text.partition(":")
    kind, name = kind.strip().lower(), name.strip()
    if not sep or kind not in ("bio", "lineup"):
        return None, f"{text!r} is not an edit target: use {USAGE}"
    if not _valid_name(kind, name):
        return None, f"{name!r} is not a valid {kind} name (letters, digits, - and _)"
    return EditTarget(kind, name), ""


def resolve(text: str, *, cwd=None, state_dir=None) -> "tuple[Optional[EditTarget], str]":
    """`parse`, plus a bare name: the bio of that name, else the lineup of that name."""
    text = (text or "").strip()
    if not text:
        return None, f"name what to edit: {USAGE}"
    if ":" in text or text == "team":
        return parse(text)
    from halo_harness.agents_yaml import find_agent_bio_path
    from halo_harness.teams_yaml import find_team_template_path
    if find_agent_bio_path(text, cwd=cwd, state_dir=state_dir):
        return parse(f"bio:{text}")
    if find_team_template_path(text, cwd=cwd, state_dir=state_dir):
        return parse(f"lineup:{text}")
    return None, f"no bio or lineup named {text!r}: use {USAGE}"
