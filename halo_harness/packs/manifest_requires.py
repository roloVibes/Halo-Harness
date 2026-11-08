"""halo_harness.packs.manifest_requires -- the tools a pack needs that Halo does not ship (Halo 3.3.12.0 R4;
docs/EXTENSION_API.md "Requirements", stable in API 1.1).

A pack that wraps an open-source tool says so in its top-level `requires:` list, beside the packs it depends on. A
pack dependency is `{pack, version}` as before (packs/resolve.py reads those); a tool is an entry with a `kind`:

    requires:
      - pack: base-docs                         # a pack it needs (unchanged)
      - kind: command                           # command | python | npm | git
        name: rg                                # the program on PATH (command), the module (python), the package (npm),
                                                # the repo's folder name (git)
        version: ">=13"                         # optional: a range, ">=x" / "<=x" / "x" (a minimum)
        install: {windows: "winget install BurntSushi.ripgrep.MSVC", linux: "sudo apt install ripgrep",
                  mac: "brew install ripgrep"}  # the line the owner runs; every one of the three
        url: https://github.com/BurntSushi/ripgrep
        license: MIT OR Unlicense
        why: searches the files the pack's command and MCP server look through
        used_by: ["mcp:rg", hooks/rg_count.py]  # optional: the pack's parts it gates (an MCP server, a pack file)

**Halo never installs a requirement.** `halo pack doctor` names a missing one (`missing-requirement`, a warns row with
the install line for this OS), `halo pack test` skips what it gates with one line, the Pack Manager's row says
"needs <name>", and the scaffold's README "Install" section is generated from the list.

    tools_of(manifest)            the tool entries (mappings with a `kind`)
    requires_lines(manifest)      one line per bad value, each naming the entry
    present(entry)                (True | False | None, how it was found); None: not checkable here (git, npm)
    install_line(entry)           the entry's install line for this OS
    doctor_rows(pack)             `missing-requirement` rows, one per tool not found here
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys

KINDS = ("command", "python", "npm", "git")
TOOL_KEYS = ("kind", "name", "version", "install", "url", "license", "why", "used_by")
OSES = ("windows", "linux", "mac")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
VERSION_RE = re.compile(r"^(>=|<=|==)? *[0-9]+([.][0-9]+){0,3}$")


def tools_of(manifest) -> "list[dict]":
    raw = manifest.get("requires") if isinstance(manifest, dict) else None
    return [e for e in raw if isinstance(e, dict) and "kind" in e] if isinstance(raw, list) else []


def is_tool(entry) -> bool:
    return isinstance(entry, dict) and "kind" in entry


def this_os() -> str:
    return "windows" if sys.platform.startswith("win") else "mac" if sys.platform == "darwin" else "linux"


def install_line(entry: dict) -> str:
    install = entry.get("install") if isinstance(entry.get("install"), dict) else {}
    line = install.get(this_os())
    return str(line).strip() if isinstance(line, str) and line.strip() else ""


def _entry_lines(i: int, e: dict, ids: "set[str]") -> "list[str]":
    where, out = f"requires[{i}]", []
    for key in e:
        if key not in TOOL_KEYS and key != "pack":
            out.append(f"{where}.{key}: not a key of a requirement (one of {', '.join(TOOL_KEYS)})")
    if "pack" in e:
        out.append(f"{where}: an entry is a pack ({{pack, version}}) or a tool ({{kind, name, ...}}), not both")
    kind, name = e.get("kind"), e.get("name")
    if kind not in KINDS:
        out.append(f"{where}.kind: {kind!r} is not one of {', '.join(KINDS)}")
    if not isinstance(name, str) or not NAME_RE.match(name):
        out.append(f"{where}.name: {name!r} is not a tool name (letters, digits, . _ + -)")
    version = e.get("version")
    if version is not None and not (isinstance(version, (str, int, float)) and VERSION_RE.match(str(version).strip())):
        out.append(f"{where}.version: {version!r} is not a range (>=1.2, <=2.0 or 1.2, a minimum)")
    install = e.get("install")
    if not isinstance(install, dict):
        out.append(f"{where}.install: required, the line the owner runs on each of {', '.join(OSES)} "
                   "(Halo never installs it)")
    else:
        missing = [o for o in OSES if not (isinstance(install.get(o), str) and install[o].strip())]
        extra = [k for k in install if k not in OSES]
        if missing:
            out.append(f"{where}.install: no line for {', '.join(missing)} (the owner's install line on each OS)")
        if extra:
            out.append(f"{where}.install: {', '.join(map(str, extra))} is not one of {', '.join(OSES)}")
    says = {"url": "where it lives", "license": "its SPDX license", "why": "what the pack uses it for"}
    for key, what in says.items():
        if not isinstance(e.get(key), str) or not e[key].strip():
            out.append(f"{where}.{key}: required ({what})")
    if isinstance(e.get("url"), str) and not re.match(r"^https?://\S+$", e["url"].strip()):
        out.append(f"{where}.url: {e['url']!r} is not an http(s) address")
    used = e.get("used_by")
    if used is not None and not (isinstance(used, list) and all(isinstance(u, str) and u.strip() for u in used)):
        out.append(f"{where}.used_by: a list of the pack's parts it gates (mcp:<server>, or a pack file)")
    if isinstance(name, str) and name in ids:
        out.append(f"{where}.name: {name!r} is required twice")
    return out


def requires_lines(manifest) -> "list[str]":
    """One line per bad value of a tool entry (a pack entry is manifest.py's)."""
    raw = manifest.get("requires") if isinstance(manifest, dict) else None
    out, ids = [], set()
    for i, e in enumerate(raw if isinstance(raw, list) else []):
        if not is_tool(e):
            continue
        out += _entry_lines(i, e, ids)
        if isinstance(e.get("name"), str):
            ids.add(e["name"])
    return out


def _git_bash_has(name: str) -> bool:
    from halo_harness.config.paths import git_bash
    bash = git_bash() if sys.platform.startswith("win") else None
    return bool(bash) and any((p / f"{name}.exe").is_file() for p in (bash.parent, bash.parent.parent / "usr" / "bin"))


def present(entry: dict) -> "tuple[object, str]":
    """Whether the tool is here: (True, where) / (False, why) / (None, why it is not checked)."""
    kind, name = entry.get("kind"), str(entry.get("name") or "")
    if kind == "command":
        found = shutil.which(name)
        return (True, found) if found else (False, f"{name} is not on PATH")
    if kind == "python":
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        return (True, f"module {name}") if spec else (False, f"Python cannot import {name} here")
    if kind == "npm":
        found = shutil.which(name)
        return (True, found) if found else (None, f"npm package {name}: not checked (no program named {name} on PATH)")
    return None, f"git repo {name}: not checked (its folder is the pack's business)"


def missing(manifest) -> "list[tuple[dict, str]]":
    """The tool entries not found here, with why (an unchecked one is not listed)."""
    out = []
    for e in tools_of(manifest):
        ok, why = present(e)
        if ok is False:
            out.append((e, why))
    return out


def gated_by(manifest, part: str) -> "list[tuple[dict, str]]":
    """The missing requirements whose `used_by` names `part` (`mcp:<server>`, or a pack file's path)."""
    return [(e, why) for e, why in missing(manifest)
            if part in [str(u).strip().replace("\\", "/") for u in e.get("used_by") or [] if isinstance(u, str)]]


def doctor_rows(pack) -> "list[dict]":
    from pathlib import Path
    out = []
    for e, why in missing(pack.manifest):
        line = install_line(e)
        used = ", ".join(str(u) for u in e.get("used_by") or []) if isinstance(e.get("used_by"), list) else ""
        out.append({"severity": "warns", "check": "missing-requirement", "path": str(Path(pack.root) / "pack.yaml"),
                    "fix": (f"install it: {line}" if line else f"install it ({e.get('url') or 'its own page'})")
                    + " -- Halo never installs a requirement",
                    "text": f"{pack.id}: needs {e.get('name')} ({e.get('kind')}): {why}"
                    + (f"; without it {used} does not run" if used else "")})
    return out


def needs_words(pack) -> "list[str]":
    """The Pack Manager's "needs <name>" words, one per missing tool."""
    return [f"needs {e.get('name')}" for e, _why in missing(pack.manifest)]
