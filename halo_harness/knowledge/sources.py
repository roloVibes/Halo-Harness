"""halo_harness.knowledge.sources -- what recall indexes besides memory, sessions
and the coach library (Halo 3.1.8.0 R4, docs/RECALL.md "Kinds" and "Your own
notes").

* `knowledge_sources(state_dir)` -- every current finding and decision
  (`<state>/knowledge/<kind>/*/*.md`): kind `finding` / `decision`, title = its
  title, the embedded text its title, body and evidence. A superseded entry is
  left out (the index prunes it), like an undone coach library entry.
* `note_sources(paths)` -- the owner's own notes: every `.md` file under each
  folder `recall.sources` names (an Obsidian vault is one), read in place and
  never written. Kind `note`; the front matter is stripped from the embedded
  text; the title is the front matter's `title`, else the first `# ` heading,
  else the file name. `.obsidian/` (and every other folder whose name starts
  with a dot) is skipped; a file over MAX_NOTE_BYTES is skipped. A note whose
  mtime matches its index entry (`known`) is not opened again.
* `report(paths)` -- `halo recall sources`: each folder, whether it is there,
  and how many notes it holds.
* `hit_fields(path)` -- a finding / decision recall hit's `ref` (its id), `by`,
  `when` and `confidence`, for `halo recall`, `/recall` and Studio's recall route.

Each source is the tuple `(id, title, text, mtime, kind)`; recall.build_index
keeps the first four and the kind.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

TEXT_CHARS = 2400
MAX_NOTE_BYTES = 2 * 1024 * 1024
NOTE = "note"


def knowledge_sources(state_dir=None) -> list:
    from halo_harness.knowledge.store import current
    out = []
    for e in current(state_dir):
        try:
            mtime = Path(e["path"]).stat().st_mtime
        except OSError:
            continue
        text = "\n".join([e["title"], e["body"]] + list(e["evidence"]) + list(e["alternatives"]))
        out.append((e["path"], e["title"], text[:TEXT_CHARS], mtime, e["kind"]))
    return out


def configured() -> list:
    """The folders `recall.sources` names (a string or a list), `~` your home (config/paths.py `home`), in
    their order, each once."""
    try:
        from halo_harness.config.paths import home
        from halo_harness.theme import get_config_value
        raw = get_config_value("recall.sources", [])
    except Exception:
        return []
    raw = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    out = []
    for item in raw:
        text = os.path.expandvars(str(item or "").strip())
        if text == "~" or text.startswith(("~/", "~\\")):
            text = str(home()) + text[1:]
        path = Path(text) if text else None
        if path is not None and path not in out:
            out.append(path)
    return out


def note_files(folder: Path) -> list:
    """Every `.md` file under `folder`, dot-folders (`.obsidian/`, `.git/`, `.trash/`) skipped, sorted."""
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        out += [Path(dirpath) / f for f in sorted(filenames) if f.lower().endswith(".md") and not f.startswith(".")]
    return out


def note_title(front: dict, body: str, path: Path) -> str:
    if isinstance(front.get("title"), str) and front["title"].strip():
        return " ".join(front["title"].split())[:200]
    heading = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith("# ") and ln[2:].strip()), "")
    return heading[:200] or path.stem


def note_sources(paths: Optional[list] = None, known: Optional[dict] = None) -> list:
    from halo_harness.config.frontmatter import parse
    out = []
    for folder in configured() if paths is None else [Path(p) for p in paths]:
        if not folder.is_dir():
            continue
        for path in note_files(folder):
            try:
                st = path.stat()
                if st.st_size > MAX_NOTE_BYTES:
                    continue
                old = (known or {}).get(str(path))
                if old is not None and old.get("mtime") == st.st_mtime:
                    out.append((str(path), old.get("title") or path.stem, None, st.st_mtime, NOTE))
                    continue
                front, body = parse(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:  # an unreadable note, or a front matter the parser cannot read: the others still go in
                continue
            title = note_title(front if isinstance(front, dict) else {}, body, path)
            out.append((str(path), title, body.strip()[:TEXT_CHARS], st.st_mtime, NOTE))
    return out


def report(paths: Optional[list] = None) -> list:
    """`[{path, exists, notes}]` for `halo recall sources`."""
    rows = []
    for folder in configured() if paths is None else [Path(p) for p in paths]:
        there = folder.is_dir()
        rows.append({"path": str(folder), "exists": there, "notes": len(note_files(folder)) if there else 0})
    return rows


def hit_fields(path: str) -> dict:
    """`{ref, by, when, confidence?}` of a finding / decision hit (its file's front matter), for a recall result."""
    from halo_harness.knowledge.store import parse, valid_id
    try:
        front, _body = parse(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}
    if not valid_id(front.get("id")):
        return {}
    out = {"ref": str(front["id"]), "by": str(front.get("by") or ""), "when": str(front.get("when") or "")}
    if front.get("confidence"):
        out["confidence"] = str(front["confidence"])
    return out
