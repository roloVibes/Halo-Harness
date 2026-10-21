"""halo_harness.packs.bio_rules -- what a pack's bio and lineup files may say
(Halo 3.2.0.0 R2, docs/PACKS.md "A pack's bios" / "A pack's lineups").

A pack's files use the same schema as yours; these lines are what a pack's
may NOT say, checked with the manifest (`manifest.validate_manifest` with a
root), one line each naming the file and its line:

- a bio names one provider: `models.provider`, or a `models.preference` /
  `models.fallback` with a route prefix (`or:`, `ant:`, `dbx:` ...), a
  vendor/model path or a Databricks endpoint name. A bare family name
  (`claude-sonnet`) may stay in `models.preference`; the rest is
  `models.capabilities` (packs/bio_models.py `TAGS`);
- `models.capabilities` that is not a list of known tags;
- `context.memory.namespace` that is not a name (letters, digits, - and _);
- `tools.needs` (the grants the bio uses): each one `mcp:<server>`, `hooks`,
  `bash`, `network` or `home-write`, and requested in pack.yaml's
  `permissions` (you grant what the pack requests);
- a lineup's `workflows` naming one the pack does not declare in
  `contributes.workflows`.

    roles_lines(manifest, root)   # [] when every file is fine
    declared_workflows(manifest)  # the names contributes.workflows declares
    bio_needs(raw)                # a bio's tools.needs as a list
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.packs import names as N

_NEED_WORDS = ("mcp:<server>", "hooks", "bash", "network", "home-write")


def declared_workflows(manifest) -> "list[str]":
    """`contributes.workflows`: names, or `workflows/<name>.yaml` files (the name is the file's stem)."""
    contributes = manifest.get("contributes") if isinstance(manifest, dict) else None
    items = contributes.get("workflows") if isinstance(contributes, dict) else None
    out = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, str) and item.strip():
            s = item.strip()
            out.append(Path(s).stem if "/" in s or s.endswith(".yaml") else s)
    return out


def bio_needs(raw) -> "list[str]":
    tools = raw.get("tools") if isinstance(raw, dict) and isinstance(raw.get("tools"), dict) else {}
    needs = tools.get("needs")
    if isinstance(needs, str):
        needs = [needs]
    return [n.strip() for n in needs if isinstance(n, str) and n.strip()] if isinstance(needs, list) else []


def _line_of(text: str, key: str, value=None) -> int:
    pat = re.compile(rf"(^|[\s{{,]){re.escape(key)}\s*:")
    for i, ln in enumerate(text.splitlines(), 1):
        if pat.search(ln) and (value is None or str(value) in ln):
            return i
    return 0


def _where(rel: str, text: str, key: str, value=None) -> str:
    n = _line_of(text, key, value)
    return f"{rel} line {n}" if n else rel


def _read(path: Path) -> "tuple[dict, str]":
    from halo_harness.agents_yaml import _read_yaml_file
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""
    return _read_yaml_file(path) or {}, text


def _model_lines(rel: str, raw: dict, text: str) -> "list[str]":
    from halo_harness.packs import bio_models as BM
    models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
    out = []
    if "provider" in models:
        out.append(f"{_where(rel, text, 'provider')}: models.provider names one provider ({models['provider']!r}); "
                   "a pack's bio says what it needs in models.capabilities")
    for key in ("preference", "fallback"):
        word = BM.provider_word(models.get(key))
        if word:
            out.append(f"{_where(rel, text, key, models[key])}: models.{key} {models[key]!r} names one provider "
                       f"({word}); a pack's bio says models.capabilities (a family name such as claude-sonnet "
                       "may stay in models.preference)")
    caps = models.get("capabilities")
    if caps is not None and not (isinstance(caps, list) and all(isinstance(c, str) for c in caps)):
        out.append(f"{_where(rel, text, 'capabilities')}: models.capabilities is a list of tags "
                   f"({', '.join(BM.TAGS)})")
    else:
        for tag in BM.unknown_tags(BM.tags_of(models)):
            out.append(f"{_where(rel, text, 'capabilities')}: models.capabilities {tag!r} is not a tag "
                       f"(one of {', '.join(BM.TAGS)})")
    return out


def _bio_lines(rel: str, raw: dict, text: str, requested: "set[str]") -> "list[str]":
    from halo_harness.packs import manifest as MF
    from halo_harness.packs.memory import raw_namespace
    out = _model_lines(rel, raw, text)
    ns = raw_namespace(raw)
    if ns and not N.is_valid_name(ns):
        out.append(f"{_where(rel, text, 'namespace')}: context.memory.namespace {ns!r} is not a name "
                   "(letters, digits, - and _)")
    tools = raw.get("tools") if isinstance(raw.get("tools"), dict) else {}
    if tools.get("needs") is not None and not isinstance(tools.get("needs"), (list, str)):
        out.append(f"{_where(rel, text, 'needs')}: tools.needs is a list ({', '.join(_NEED_WORDS)})")
    for need in bio_needs(raw):
        if not (need.startswith(MF.MCP_PREFIX) and len(need) > len(MF.MCP_PREFIX)) and need not in MF.PERMISSIONS:
            out.append(f"{_where(rel, text, 'needs')}: tools.needs {need!r} is not one of {', '.join(_NEED_WORDS)}")
        elif need not in requested:
            out.append(f"{_where(rel, text, 'needs')}: tools.needs {need!r} is not in pack.yaml's permissions "
                       "(request it there, so you can grant it)")
    return out


def _lineup_lines(rel: str, raw: dict, text: str, declared: "list[str]") -> "list[str]":
    flows = raw.get("workflows")
    if flows is None:
        return []
    if not (isinstance(flows, list) and all(isinstance(f, str) for f in flows)):
        return [f"{_where(rel, text, 'workflows')}: workflows is a list of the pack's workflow names"]
    have = ", ".join(declared) or "none declared"
    return [f"{_where(rel, text, 'workflows')}: workflows {f!r} is not one of the pack's contributes.workflows "
            f"({have})" for f in flows if f not in declared]


def roles_lines(manifest: dict, root) -> "list[str]":
    from halo_harness.packs import manifest as MF
    root = Path(root)
    requested = set(MF.requested(manifest))
    out: "list[str]" = []
    for path in sorted((root / "agents").glob("*.yaml")) if (root / "agents").is_dir() else []:
        raw, text = _read(path)
        out += _bio_lines(f"agents/{path.name}", raw, text, requested)
    declared = declared_workflows(manifest)
    for path in sorted((root / "teams").glob("*.yaml")) if (root / "teams").is_dir() else []:
        if path.name.endswith(".team.yaml"):
            continue
        raw, text = _read(path)
        out += _lineup_lines(f"teams/{path.name}", raw, text, declared)
    return out
