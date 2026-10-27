"""halo_harness.studio.settings_door -- the door into Studio's Settings section (Halo 3.3.3.0 R2), the
studio/setup_door.py pattern:

    SettingsTarget()                Settings                 ?mode=settings
    SettingsTarget(group="fleet")   Settings, the Fleet page ?mode=settings&group=fleet   (`halo settings fleet`)

It travels as an edit-target text (`settings`, `settings:fleet`), so `halo studio --edit settings:fleet`, the
detached Studio's argv and `launch.url_from_info` all carry it (studio/edit_target.py hands the `settings` kind to
`parse` here); a Studio page already open gets it as a `focus` frame `{edit: "", mode: "settings", group}`
(ui/src/routes/settings/door.ts reads `?group=` once and drops it from the address). `setup_door.open_setup` and
`setup_door.cli_door` open it the way they open Setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def group_word(word: str) -> "tuple[Optional[str], str]":
    """`(group id, '')` for a group's id or title ('' = the page last open), or `(None, why)`."""
    from halo_harness.settings_catalog import GROUPS
    w = (word or "").strip().lower()
    if not w:
        return "", ""
    for gid, title in GROUPS:
        if w in (gid, title.lower(), title.lower().split()[0]):
            return gid, ""
    return None, f"{word!r} is not a Settings group: use one of {', '.join(g for g, _ in GROUPS)}"


@dataclass(frozen=True)
class SettingsTarget:
    group: str = ""

    @property
    def mode(self) -> str:
        return "settings"

    @property
    def text(self) -> str:
        """The edit-target text: `settings` or `settings:<group>`."""
        return f"settings:{self.group}" if self.group else "settings"

    @property
    def display(self) -> str:
        from halo_harness.settings_catalog import GROUP_TITLES
        return f"Settings ({GROUP_TITLES[self.group]})" if self.group in GROUP_TITLES else "Settings"

    @property
    def verb(self) -> str:
        return "change"

    @property
    def cli(self) -> str:
        return f"halo studio --edit {self.text}"

    def query(self) -> str:
        return "?mode=settings" + (f"&group={self.group}" if self.group else "")

    def focus(self) -> dict:
        """The `focus` frame's data, and POST /api/focus's body."""
        return {"edit": "", "mode": "settings", "session": "", "group": self.group}


def parse(text: str) -> "tuple[Optional[SettingsTarget], str]":
    """`settings` or `settings:<group>` -> the target; `(None, why)` for anything else."""
    kind, _sep, rest = (text or "").strip().partition(":")
    if kind.strip().lower() != "settings":
        return None, f"{text!r} is not a Settings target"
    group, why = group_word(rest)
    return (SettingsTarget(group=group), "") if group is not None else (None, why)
