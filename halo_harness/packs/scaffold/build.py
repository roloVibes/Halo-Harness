"""halo_harness.packs.scaffold.build -- the files of a new pack, in memory (Halo 3.3.12.0 R4).

    plan(values, kinds, github=True, license="MIT") -> (manifest dict, {relative path: text})

`values` fills the placeholders (`__ID__`, `__NAME__`, `__DESCRIPTION__`, `__AUTHOR__`, `__LICENSE__`, `__YEAR__`,
`__HALO_VERSION__`): in a manifest fragment they are filled after it is read as YAML, so a name with a colon or a
quote stays a plain string. Fragments merge key by key; lists add up (a scalar item once). A JSON file two kinds
both write (`.mcp.json`, `hooks/hooks.json`) is merged the same way. `dot-x` in the kit is `.x` in the pack.
"""

from __future__ import annotations

import json
from pathlib import Path

from halo_harness.packs.scaffold.kinds import kit_dir

HEADER = ("# {name} ({id}): a Halo pack made with `halo pack new`. HALO-PACK.md says how to work on it; README.md\n"
          "# lists every file. Every value here is checked at install: `halo pack test .` runs every check.\n")


def fill(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace(f"__{key}__", str(value))
    return text


def fill_data(data, values: dict):
    if isinstance(data, str):
        return fill(data, values)
    if isinstance(data, list):
        return [fill_data(x, values) for x in data]
    if isinstance(data, dict):
        return {fill(str(k), values): fill_data(v, values) for k, v in data.items()}
    return data


def merge(a, b):
    """`b` into `a`: mappings key by key, lists added up (a scalar once), anything else `b`'s."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = merge(out[k], v) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = list(a)
        for item in b:
            if isinstance(item, (dict, list)) or item not in out:
                out.append(item)
        return out
    return b


def _read_yaml(path: Path) -> dict:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return data if isinstance(data, dict) else {}


def _dest(rel: Path) -> str:
    return "/".join(("." + p[4:]) if p.startswith("dot-") else p for p in rel.parts)


def _files(folder: Path) -> "dict[str, str]":
    out = {}
    if folder.is_dir():
        for p in sorted(folder.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out[_dest(p.relative_to(folder))] = p.read_text(encoding="utf-8")
    return out


def _add(files: dict, rel: str, text: str) -> None:
    if rel in files and rel.endswith(".json"):
        files[rel] = json.dumps(merge(json.loads(files[rel]), json.loads(text)), indent=2) + "\n"
    else:
        files[rel] = text


def order(manifest: dict) -> dict:
    """pack.yaml's keys in the manifest's order (schemas/pack_yaml.py), `contributes` too."""
    from halo_harness.schemas.pack_yaml import CONTRIBUTION_KEYS, TOP_KEYS
    out = {k: manifest[k] for k in TOP_KEYS if k in manifest}
    out.update({k: v for k, v in manifest.items() if k not in out})
    c = out.get("contributes")
    if isinstance(c, dict):
        out["contributes"] = {**{k: c[k] for k in CONTRIBUTION_KEYS if k in c},
                              **{k: v for k, v in c.items() if k not in CONTRIBUTION_KEYS}}
    if isinstance(out.get("permissions"), list):
        out["permissions"] = list(dict.fromkeys(out["permissions"]))
    return out


def _dumper():
    """safe_dump's dumper, with a short list of plain values on one line ([a, b]) and a text of several lines as a
    block (|-), the way a person writes pack.yaml."""
    import yaml

    class Dumper(yaml.SafeDumper):
        pass

    def strings(d, value):
        style = "|" if "\n" in value else None
        return d.represent_scalar("tag:yaml.org,2002:str", value, style=style)

    def lists(d, value):
        flat = all(isinstance(v, (str, int, float, bool)) and "\n" not in str(v) for v in value)
        return d.represent_sequence("tag:yaml.org,2002:seq", value,
                                    flow_style=flat and len(", ".join(map(str, value))) < 70)

    Dumper.add_representer(str, strings)
    Dumper.add_representer(list, lists)
    return Dumper


def manifest_text(manifest: dict) -> str:
    import yaml
    body = yaml.dump(manifest, Dumper=_dumper(), sort_keys=False, default_flow_style=False, allow_unicode=True,
                     width=110)
    return HEADER.format(name=manifest.get("name"), id=manifest.get("id")) + body


def plan(values: dict, kinds, *, github: bool = True, license_id: str = "MIT") -> "tuple[dict, dict]":
    kit = kit_dir()
    manifest = fill_data(_read_yaml(kit / "base" / "manifest.yaml"), values)
    files: "dict[str, str]" = {}
    for rel, text in _files(kit / "base" / "files").items():
        _add(files, rel, fill(text, values))
    for kind in kinds:
        manifest = merge(manifest, fill_data(_read_yaml(kit / "kinds" / kind / "manifest.yaml"), values))
        for rel, text in _files(kit / "kinds" / kind / "files").items():
            _add(files, rel, fill(text, values))
    if github:
        for rel, text in _files(kit / "github" / "files").items():
            _add(files, rel, fill(text, values))
        name = "LICENSE-MIT" if license_id == "MIT" else "LICENSE-OTHER"
        files["LICENSE"] = fill((kit / "github" / name).read_text(encoding="utf-8"), values)
    _seams(files, kinds, values)
    return order(manifest), files


def _seams(files: dict, kinds, values: dict) -> None:
    """The lines a file carries only with another kind: the lineup's workflows, the policy's own test."""
    crew = "teams/crew.yaml"
    if crew in files:
        files[crew] = files[crew].replace("#__WORKFLOWS__\n", "workflows: [flow]\n" if "workflows" in kinds else "")
    test = "tests/pack_test.py"
    own = ""
    if "policy" in kinds:
        own = fill(
            '    deny = testing.ask_policy(PACK, "guard", "Write", {"file_path": ".git/config", "content": "x"})\n'
            '    report.add("policy/guard.py", "a Write under .git/ is denied", deny.get("verdict") == "deny",\n'
            '               "guard.py denies a write whose path has a .git folder in it")\n', values)
    files[test] = files[test].replace("# __OWN_CHECKS__\n", own)
