"""halo_harness.packs.names -- a pack's id, the names it gives its bios and
lineups, and the source label its files carry (Halo 3.2.0.0 R1).

    is_valid_pack_id("doc-review")        # ^[a-z][a-z0-9-]*$
    qualify("doc-review", "reviewer")     # "doc-review--reviewer"
    unqualify("doc-review--reviewer")     # ("doc-review", "reviewer")
    pack_source("doc-review")             # "pack:doc-review"
    read_only_source("pack:doc-review")   # True (and for "template")

A pack's bio or lineup is listed under `<id>--<name>`: valid under the bio
and lineup name rule (`^[A-Za-z0-9][A-Za-z0-9_-]*$`), so it works as a route
target, a memory folder name and a `tools.mcp_servers` entry. An id never
holds `--` and never ends in `-`, so a qualified name splits one way only.
"""

from __future__ import annotations

import re
from typing import Optional

PACK_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SEP = "--"
SOURCE_PREFIX = "pack:"
#: The shipped folder's label (agents_yaml / teams_yaml); read-only like a pack's.
TEMPLATE_SOURCE = "template"


def is_valid_pack_id(pack_id) -> bool:
    return (isinstance(pack_id, str) and bool(PACK_ID_RE.match(pack_id)) and SEP not in pack_id
            and not pack_id.endswith("-") and len(pack_id) <= 64)


def pack_id_problem(pack_id) -> str:
    """One line naming what is wrong with `pack_id`, or ''."""
    if is_valid_pack_id(pack_id):
        return ""
    return (f"id {pack_id!r} is not a pack id: lower-case letters, digits and single hyphens, starting with a "
            "letter, at most 64 characters (doc-review)")


def is_valid_name(name) -> bool:
    """The bio and lineup name rule (agents_yaml / teams_yaml)."""
    return isinstance(name, str) and bool(NAME_RE.match(name)) and ".." not in name


def qualify(pack_id: str, name: str) -> str:
    return f"{pack_id}{SEP}{name}"


def unqualify(name) -> "tuple[Optional[str], str]":
    """`("doc-review", "reviewer")` for `doc-review--reviewer`; `(None, name)` for a bare name."""
    if not isinstance(name, str) or SEP not in name:
        return None, name
    pack_id, rest = name.split(SEP, 1)
    return (pack_id, rest) if is_valid_pack_id(pack_id) and rest else (None, name)


def pack_source(pack_id: str) -> str:
    return f"{SOURCE_PREFIX}{pack_id}"


def pack_of_source(label) -> Optional[str]:
    """The pack id a `pack:<id>` label names, else None."""
    if isinstance(label, str) and label.startswith(SOURCE_PREFIX):
        return label[len(SOURCE_PREFIX):] or None
    return None


def read_only_source(label) -> bool:
    """True for a file Halo never writes: the shipped templates and every pack's files."""
    return label == TEMPLATE_SOURCE or pack_of_source(label) is not None


def scope_label(label) -> str:
    """How a list shows a source: "shipped", "pack <id>", else the label itself."""
    if label == TEMPLATE_SOURCE:
        return "shipped"
    pack_id = pack_of_source(label)
    return f"pack {pack_id}" if pack_id else str(label or "?")


def is_url(source) -> bool:
    """A git url (`https://`, `http://`, `ssh://`, `git://`, `file://`, `git@host:path`), not a folder."""
    if not isinstance(source, str):
        return False
    s = source.strip()
    return bool(re.match(r"^(https?|ssh|git|file)://", s)) or bool(re.match(r"^[\w.-]+@[\w.-]+:", s))
