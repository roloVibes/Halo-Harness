"""halo_harness.packs.scaffold -- `halo pack new <id>`: a complete pack that installs, passes `halo pack test` and
that `halo pack doctor` finds nothing wrong with (Halo 3.3.12.0 R4; docs/PACK-AUTHORING.md).

    new(pack_id, kinds=(), all_kinds=False, folder=None, github=True, license_id="MIT", name="", description="",
        author="") -> (ok, lines)

The pack is written to `<folder>/<id>/` (the current folder when `folder` is None); a folder already there is left
as it is and the answer is one line. Every file goes through one write each, LF endings; nothing outside the new
folder is written. The templates are `halo_harness/templates/pack-kit/` (kinds.py says the layout).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

SPDX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*( (OR|AND|WITH) [A-Za-z0-9][A-Za-z0-9.+-]*)*$")


def _title(pack_id: str) -> str:
    return " ".join(w.capitalize() for w in pack_id.split("-"))


def _values(pack_id: str, name: str, description: str, author: str, license_id: str) -> dict:
    from halo_harness import __version__
    name = name or _title(pack_id)
    return {"ID": pack_id, "NAME": name, "AUTHOR": author or "the pack's author", "LICENSE": license_id,
            "DESCRIPTION": description or f"{name}: a Halo pack made with halo pack new; say here what it does.",
            "YEAR": time.strftime("%Y"), "HALO_VERSION": __version__}


def files_for(pack_id: str, kinds, *, github: bool = True, license_id: str = "MIT", name: str = "",
              description: str = "", author: str = "") -> "tuple[dict, dict]":
    """The new pack's manifest and every file `{relative path: text}`, nothing written."""
    from halo_harness.packs.scaffold import build, docs
    values = _values(pack_id, name, description, author, license_id)
    manifest, files = build.plan(values, kinds, github=github, license_id=license_id)
    files["pack.yaml"] = build.manifest_text(manifest)
    files[f"commands/{pack_id}.md"] = docs.entry_command(manifest, files)
    files["HALO-PACK.md"] = build.fill(files["HALO-PACK.md"], {"WHAT_IT_BRINGS": docs.brings(manifest, files)})
    files["README.md"] = docs.readme(manifest, files, github=github)
    return manifest, files


def new(pack_id: str, *, kinds=(), all_kinds: bool = False, folder=None, github: bool = True, license_id: str = "MIT",
        name: str = "", description: str = "", author: str = "") -> "tuple[bool, list[str]]":
    from halo_harness.packs.names import pack_id_problem
    from halo_harness.packs.scaffold import kinds as K
    problem = pack_id_problem(pack_id)
    if problem:
        return False, [problem]
    if not SPDX.match(license_id or ""):
        return False, [f"--license {license_id!r} is not an SPDX id (MIT, Apache-2.0, MIT OR Apache-2.0)"]
    lines: "list[str]" = []
    asked = list(K.KINDS) if all_kinds else list(kinds)
    if "themes" in asked and not K.themes_known():
        if not all_kinds:
            return False, [K.themes_line().replace("the kind is left out", "leave it out of --kinds")]
        asked.remove("themes")
        lines.append(K.themes_line())
    chosen, added = K.expand(asked)
    dest = Path(folder if folder is not None else Path.cwd()).expanduser().resolve() / pack_id
    if dest.exists():
        return False, [f"{dest} is already there; halo pack new writes a new folder only (pick another id or --dir)"]
    _manifest, files = files_for(pack_id, chosen, github=github, license_id=license_id, name=name,
                                 description=description, author=author)
    try:
        for rel, text in sorted(files.items()):
            path = dest / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    except OSError as e:
        return False, [f"halo pack new stopped writing {dest}: {e}"]
    shown = dest.as_posix()
    lines = [f"made {pack_id} at {shown}: {len(files)} files",
             "kinds: " + (", ".join(chosen) if chosen else "none (the base: the entry command, the manifest, the docs)")
             ] + lines + added
    lines += [f"entry command: /{pack_id} (commands/{pack_id}.md), once the pack is enabled",
              f"next: cd {shown} && halo pack test .",
              "then: halo pack install . --link --project, and halo pack enable " + pack_id + " --grant-all",
              "HALO-PACK.md is what a Halo session follows in that folder (halo --team pack-author)"]
    return True, lines
