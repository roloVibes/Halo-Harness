"""halo_harness.teams_bundle -- Halo 2.0.6 round 13: export/import of a
lineup with its bios as one folder (the roadmap's own "export/import
bundles" item, deferred from 2.0.5 round 2).

`bundle_export(name, out_dir)`: writes the FULL team template plus every
NON-shipped bio it references (project/user scope -- a shipped template's
bios already exist on every install) into one folder:

    <out_dir>/
      bundle.json          # {name, version, bios: [...]}
      team.yaml            # the template verbatim (minus _-prefixed keys)
      bios/<bio-name>.yaml # one per referenced bio

`bundle_import(dir)`: reads that folder -- every bio lands in USER scope
(`~/.halo/agents/`, the scope every machine shares), the team through the
SAME `save_team_template` path `halo teams import` already uses (full
validation). A bio name that already exists in user scope is NEVER
silently overwritten: `--force` is the explicit opt-in, else the import
reports the collision and skips that bio.

Round-trip safe: a bundle exported on one box imports on another with
zero hand-editing -- exactly the manual scp the owner did tonight for
the halo-dev-cycle lineup.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional


def _template_bio_names(template: dict) -> "list[str]":
    """Every `agent:` name the lineup references, in order, deduped."""
    names: "list[str]" = []
    for entry in (template.get("agents") or []):
        if isinstance(entry, dict):
            name = entry.get("agent")
            if isinstance(name, str) and name.strip() and name not in names:
                names.append(name.strip())
    return names


def bundle_export(name: str, out_dir, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`(ok, lines)` -- the folder written on success, the problems on
    failure (never a partial bundle: nothing is written unless every
    referenced non-shipped bio resolves)."""
    from halo_harness.agents_yaml import find_agent_bio_path
    from halo_harness.teams_yaml import resolve_team_template
    template = resolve_team_template(name, cwd=cwd, state_dir=state_dir)
    if template is None:
        return False, [f"no such team template {name!r}"]

    import yaml
    payload = {k: v for k, v in template.items() if not k.startswith("_")}
    bios: "list[tuple[str, Path]]" = []
    skipped: "list[str]" = []
    for bio_name in _template_bio_names(template):
        found = find_agent_bio_path(bio_name, cwd=cwd, state_dir=state_dir)
        if found is None:
            return False, [f"agent bio {bio_name!r} referenced by the lineup does not resolve"]
        path, source = found
        if source == "template":
            skipped.append(bio_name)  # shipped -- every install already has it
            continue
        bios.append((bio_name, path))

    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        return False, [f"{out} exists and is not empty"]
    (out / "bios").mkdir(parents=True, exist_ok=True)
    try:
        (out / "team.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True),
            encoding="utf-8")
        copied: "list[str]" = []
        for bio_name, path in bios:
            shutil.copyfile(path, out / "bios" / f"{bio_name}.yaml")
            copied.append(bio_name)
        (out / "bundle.json").write_text(json.dumps({
            "bundle": "halo-team", "version": 1, "name": name,
            "team_version": template.get("version"), "bios": copied,
            "shipped_bios_skipped": skipped,
        }, indent=2), encoding="utf-8")
    except OSError as e:
        shutil.rmtree(out, ignore_errors=True)
        return False, [f"write failed: {e}"]
    lines = [f"bundled team {name!r} -> {out}",
             f"  bios copied: {', '.join(copied) if copied else '(none -- all shipped templates)'}"]
    if skipped:
        lines.append(f"  shipped bios skipped (already on every install): {', '.join(skipped)}")
    return True, lines


def bundle_import(dir_path, *, force: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`(ok, lines)` -- the folder `bundle_export` wrote, applied: bios to
    USER scope, the team through the validated save path."""
    from halo_harness.agents_yaml import find_agent_bio_path, user_agents_dir
    from halo_harness.teams_yaml import save_team_template
    import yaml
    d = Path(dir_path)
    manifest_path = d / "bundle.json"
    team_path = d / "team.yaml"
    if not manifest_path.is_file() or not team_path.is_file():
        return False, [f"{d} is not a halo team bundle (no bundle.json/team.yaml)"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, [f"bundle.json is unreadable: {e}"]
    try:
        team = yaml.safe_load(team_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        return False, [f"team.yaml is not valid YAML: {e}"]
    if not isinstance(team, dict):
        return False, ["team.yaml is not a team template"]

    name = manifest.get("name") or team.get("name")
    if not isinstance(name, str) or not name.strip():
        return False, ["the bundle names no team"]

    lines: "list[str]" = []
    copied, skipped = [], []
    user_dir = user_agents_dir(state_dir)
    for bio_file in sorted((d / "bios").glob("*.yaml")) if (d / "bios").is_dir() else []:
        bio_name = bio_file.stem
        existing = find_agent_bio_path(bio_name, cwd=cwd, state_dir=state_dir)
        if existing is not None and existing[1] != "template" and not force:
            skipped.append(f"{bio_name} (exists in {existing[1]} scope; --force overwrites)")
            continue
        user_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bio_file, user_dir / f"{bio_name}.yaml")
        copied.append(bio_name)

    ok, problems = save_team_template(name, team, cwd=cwd, state_dir=state_dir)
    if not ok:
        # 2.0.6 review finding 3 (minor, fixed): bios copied BEFORE the
        # team save used to be left behind when the save failed -- roll
        # back the copies this import itself made (never a file that
        # existed before: those were skipped above unless --force, and
        # --force means the user explicitly chose overwrite semantics).
        for bio_name in copied:
            try:
                (user_dir / f"{bio_name}.yaml").unlink()
            except OSError:
                pass
        return False, [*(f"team: {p}" for p in problems)]
    lines.append(f"imported team {name!r}")
    lines.append(f"  bios copied to user scope: {', '.join(copied) if copied else '(none)'}")
    if skipped:
        lines.append(f"  bios SKIPPED: {'; '.join(skipped)}")
    lines.append(f"  activate with: halo teams use {name}")
    return True, lines
