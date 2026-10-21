"""halo_harness.packs.memory -- a pack bio's own memory namespace (Halo
3.2.0.0 R2, docs/PACKS.md "A pack's bios").

A bio already names its memory namespace in `context.memory.namespace`
(Studio's "Memory namespace" field). In a pack's bio it defaults to the
pack's id, and it always lives under that pack: `<id>/<namespace>`, the
folder `~/.halo/packs/.data/<id>/memory/<namespace>/`. Recall keys every
entry by its file's path (halo_harness/recall.py), so the namespace IS the
folder: `recall.search(..., namespace="doc-review/doc-review")` reads only
that folder's notes, and a search with no namespace (yours, as before)
leaves every pack's folder out. Two packs never share a folder; two bios of
one pack that name the same namespace do.

    bio_namespace(bio)                  # "doc-review/doc-review" for a pack bio, None for yours
    namespace_dir(ns, state_dir=...)    # its folder
    namespace_of_path(path, state_dir=...)  # the namespace a file belongs to, "" for yours
    memory_sources(state_dir=...)       # (id, title, text, mtime) per note, for recall's index
    member_note(bio, state_dir)         # (folder, prompt line) for a team member on a pack bio, or (None, "")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N

MEMORY = "memory"


def _data_root(state_dir=None) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir) / ".data"


def raw_namespace(bio) -> str:
    """The namespace a bio's `context.memory` names ('' when none): a mapping's `namespace`."""
    context = bio.get("context") if isinstance(bio, dict) and isinstance(bio.get("context"), dict) else {}
    memory = context.get("memory")
    if isinstance(memory, dict) and isinstance(memory.get("namespace"), str):
        return memory["namespace"].strip()
    return ""


def bio_namespace(bio) -> Optional[str]:
    """`<id>/<namespace>` for a pack's bio (the namespace defaults to the id); None for a bio of yours."""
    pack_id = bio.get("_pack") if isinstance(bio, dict) else None
    if not isinstance(pack_id, str) or not N.is_valid_pack_id(pack_id):
        return None
    ns = raw_namespace(bio) or pack_id
    return f"{pack_id}/{ns}" if N.is_valid_name(ns) else None


def namespace_dir(namespace: str, *, state_dir=None) -> Path:
    pack_id, _sep, ns = str(namespace).partition("/")
    return _data_root(state_dir) / pack_id / MEMORY / ns


def namespace_of_path(path, *, state_dir=None) -> str:
    """`<id>/<namespace>` when `path` is a note in a pack's memory folder, '' otherwise (yours)."""
    root, raw = str(_data_root(state_dir)), str(Path(path))
    if not os.path.normcase(raw).startswith(os.path.normcase(root) + os.sep):
        return ""
    parts = Path(raw[len(root) + 1:]).parts
    return f"{parts[0]}/{parts[2]}" if len(parts) >= 4 and parts[1].lower() == MEMORY else ""


def memory_sources(*, state_dir=None) -> list:
    """(id, title, text, mtime) for every note (`*.md`) in every pack's memory folders."""
    out = []
    root = _data_root(state_dir)
    for path in sorted(root.glob(f"*/{MEMORY}/*/*.md")) if root.is_dir() else []:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            out.append((str(path), path.stem, text, path.stat().st_mtime))
        except OSError:
            continue
    return out


def in_namespace(entry_id: str, namespace: Optional[str], *, state_dir=None) -> bool:
    """Whether recall's entry belongs to `namespace` (None: yours, so not in any pack's folder)."""
    return namespace_of_path(entry_id, state_dir=state_dir) == (namespace or "")


def member_note(bio, state_dir) -> "tuple[Optional[Path], str]":
    """A team member running a pack's bio: its memory folder and the prompt line naming it."""
    ns = bio_namespace(bio) if isinstance(bio, dict) else None
    if not ns:
        return None, ""
    folder = namespace_dir(ns, state_dir=state_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None, ""
    return folder, (f"Your memory namespace ({ns}, from pack {ns.split('/')[0]}): {folder} -- notes you write "
                    "there are this namespace's only; recall over it never mixes with another pack's or the user's.")
