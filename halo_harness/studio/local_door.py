"""halo_harness.studio.local_door -- the door into Studio's Local section (Halo 3.3.5.0 R1), the
studio/settings_door.py pattern:

    LocalTarget()                  Local, the page last open      ?mode=local
    LocalTarget(page="hosts")      Local, the Hosts page          ?mode=local&page=hosts   (`halo local` opens it)

It travels as an edit-target text (`local`, `local:hosts`), so `halo studio --edit local:hosts`, the detached
Studio's argv and `launch.url_from_info` all carry it (studio/edit_target.py hands the `local` kind to `parse`
here); a Studio page already open gets it as a `focus` frame `{edit: "", mode: "local", page}`
(ui/src/routes/local/door.ts reads `?page=` once and drops it from the address).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

PAGES = (("resources", "Resources"), ("hosts", "Hosts"), ("models", "Models"), ("library", "Library"),
         ("huggingface", "Hugging Face"), ("benchmarks", "Benchmarks"), ("steward", "Steward"))
TITLES = dict(PAGES)


def page_word(word: str) -> "tuple[Optional[str], str]":
    """`(page id, '')` for a page's id or title ('' = the page last open), or `(None, why)`."""
    w = (word or "").strip().lower().replace(" ", "")
    if not w:
        return "", ""
    for pid, title in PAGES:
        if w in (pid, title.lower().replace(" ", ""), "hf" if pid == "huggingface" else pid):
            return pid, ""
    return None, f"{word!r} is not a Local page: use one of {', '.join(p for p, _ in PAGES)}"


@dataclass(frozen=True)
class LocalTarget:
    page: str = ""

    @property
    def mode(self) -> str:
        return "local"

    @property
    def text(self) -> str:
        return f"local:{self.page}" if self.page else "local"

    @property
    def display(self) -> str:
        return f"Local ({TITLES[self.page]})" if self.page in TITLES else "Local"

    @property
    def verb(self) -> str:
        return "watch"

    @property
    def cli(self) -> str:
        return f"halo studio --edit {self.text}"

    def query(self) -> str:
        return "?mode=local" + (f"&page={self.page}" if self.page else "")

    def focus(self) -> dict:
        """The `focus` frame's data, and POST /api/focus's body."""
        return {"edit": "", "mode": "local", "session": "", "page": self.page}


def parse(text: str) -> "tuple[Optional[LocalTarget], str]":
    """`local` or `local:<page>` -> the target; `(None, why)` for anything else."""
    kind, _sep, rest = (text or "").strip().partition(":")
    if kind.strip().lower() != "local":
        return None, f"{text!r} is not a Local target"
    page, why = page_word(rest)
    return (LocalTarget(page=page), "") if page is not None else (None, why)
