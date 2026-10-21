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
validation). Every bio is validated (`validate_agent_bio`, with `extends:`
checked against the bundle's own bios too) before anything is written; one
invalid bio refuses the whole import. A bio name that already exists in
user or project scope is NEVER silently overwritten: `--force` is the
explicit opt-in, else the import reports the collision and skips that bio.
A bio named like a SHIPPED one is installed and shadows it on this machine;
the import says so in a "shadows shipped bio(s)" line.

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
    from halo_harness.packs.names import pack_of_source, read_only_source
    payload = {k: v for k, v in template.items() if not k.startswith("_")}
    bios: "list[tuple[str, Path]]" = []
    skipped: "list[str]" = []
    from_packs: "list[str]" = []  # 3.2.0.0 R1: a pack's bio comes with the pack, never in a bundle
    for bio_name in _template_bio_names(template):
        found = find_agent_bio_path(bio_name, cwd=cwd, state_dir=state_dir)
        if found is None:
            return False, [f"agent bio {bio_name!r} referenced by the lineup does not resolve"]
        path, source = found
        if read_only_source(source):
            if pack_of_source(source):
                from_packs.append(f"{bio_name} (pack {pack_of_source(source)})")
            else:
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
            "shipped_bios_skipped": skipped, "pack_bios_skipped": from_packs,
        }, indent=2), encoding="utf-8")
    except OSError as e:
        shutil.rmtree(out, ignore_errors=True)
        return False, [f"write failed: {e}"]
    lines = [f"bundled team {name!r} -> {out}",
             f"  bios copied: {', '.join(copied) if copied else '(none -- all shipped templates)'}"]
    if skipped:
        lines.append(f"  shipped bios skipped (already on every install): {', '.join(skipped)}")
    if from_packs:
        lines.append(f"  pack bios skipped (install the pack where you import this): {', '.join(from_packs)}")
    return True, lines


def bundle_import(dir_path, *, force: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`(ok, lines)` -- the folder `bundle_export` wrote, applied: bios to
    USER scope, the team through the validated save path."""
    from halo_harness.agents_yaml import _write_yaml_file, find_agent_bio_path, user_agents_dir
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

    # 3.0.1.0 review item 54: every bio is read and validated BEFORE
    # anything is written -- one bad bio refuses the whole import.
    bundle_bios, problems = _read_bundle_bios(d)
    problems += _validate_bundle_bios(bundle_bios, cwd=cwd, state_dir=state_dir)
    if problems:
        return False, problems

    from halo_harness.packs.names import read_only_source
    lines: "list[str]" = []
    copied, skipped, shadowed = [], [], []
    previous: "dict[str, bytes]" = {}
    user_dir = user_agents_dir(state_dir)
    for bio_name, data in bundle_bios.items():
        existing = find_agent_bio_path(bio_name, cwd=cwd, state_dir=state_dir)
        if existing is not None and not read_only_source(existing[1]) and not force:
            skipped.append(f"{bio_name} (exists in {existing[1]} scope; --force overwrites)")
            continue
        target = user_dir / f"{bio_name}.yaml"
        if target.is_file():
            try:
                previous[bio_name] = target.read_bytes()
            except OSError:
                pass
        payload = {k: v for k, v in data.items() if not str(k).startswith("_")}
        payload["name"] = bio_name
        try:
            _write_yaml_file(target, payload)
        except OSError as e:
            _roll_back_bios(user_dir, copied, previous)
            return False, [f"bio {bio_name}: write failed: {e}"]
        copied.append(bio_name)
        if existing is not None and read_only_source(existing[1]):  # shipped, or a pack's (3.2.0.0 R1)
            shadowed.append(bio_name if existing[1] == "template" else f"{bio_name} (pack {existing[1][5:]})")

    ok, problems = save_team_template(name, team, cwd=cwd, state_dir=state_dir)
    if not ok:
        # 2.0.6 review finding 3 (minor, fixed): bios copied BEFORE the
        # team save used to be left behind when the save failed -- roll
        # back the copies this import itself made; a user bio a --force
        # import overwrote gets its previous content back.
        _roll_back_bios(user_dir, copied, previous)
        return False, [*(f"team: {p}" for p in problems)]
    lines.append(f"imported team {name!r}")
    lines.append(f"  bios copied to user scope: {', '.join(copied) if copied else '(none)'}")
    if skipped:
        lines.append(f"  bios SKIPPED: {'; '.join(skipped)}")
    if shadowed:
        lines.append(f"  shadows shipped or pack bio(s): {', '.join(shadowed)} -- every lineup on this machine "
                     f"that assigns them now uses the bundle's copy")
    lines.append(f"  activate with: halo teams use {name}")
    return True, lines


def _read_bundle_bios(d: Path) -> "tuple[dict, list[str]]":
    """`({stem: data}, problems)` for every `bios/*.yaml` in the bundle."""
    import yaml
    from halo_harness.agents_yaml import is_valid_agent_name
    bios: dict = {}
    problems: "list[str]" = []
    bios_dir = d / "bios"
    for bio_file in sorted(bios_dir.glob("*.yaml")) if bios_dir.is_dir() else []:
        stem = bio_file.stem
        if not is_valid_agent_name(stem):
            problems.append(f"bio {stem}: {stem!r} is not a valid agent name")
            continue
        try:
            data = yaml.safe_load(bio_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            problems.append(f"bio {stem}: not readable YAML: {e}")
            continue
        if not isinstance(data, dict):
            problems.append(f"bio {stem}: bio must be a YAML mapping (top-level key: value)")
            continue
        bios[stem] = data
    return bios, problems


def _validate_bundle_bios(bios: dict, *, cwd=None, state_dir=None) -> "list[str]":
    """`validate_agent_bio` on each bio, with `extends:` resolved against
    the bundle's own bios first (a bundle whose bios extend each other is
    fine) and then the installed ones."""
    from halo_harness.agents_yaml import load_agent_bio_raw, validate_agent_bio
    problems: "list[str]" = []
    for stem, data in bios.items():
        body = {k: v for k, v in data.items() if k != "extends"}
        problems.extend(f"bio {stem}: {p}" for p in validate_agent_bio(body, name=stem, cwd=cwd, state_dir=state_dir))
        parent = data.get("extends")
        if parent is None:
            continue
        if not isinstance(parent, str) or not parent.strip():
            problems.append(f'bio {stem}: "extends" must be a non-empty string')
            continue
        chain = [stem]
        current = parent.strip()
        while True:
            if current in chain:
                problems.append(f'bio {stem}: "extends" forms a cycle: {" -> ".join(chain + [current])}')
                break
            chain.append(current)
            found = bios.get(current)
            if found is None:
                found = load_agent_bio_raw(current, cwd=cwd, state_dir=state_dir)
            if found is None:
                if len(chain) == 2:
                    problems.append(f'bio {stem}: "extends" names an agent bio that does not exist: {current!r}')
                break
            nxt = found.get("extends")
            if not isinstance(nxt, str) or not nxt.strip():
                break
            current = nxt.strip()
    return problems


def _roll_back_bios(user_dir: Path, copied: "list[str]", previous: "dict[str, bytes]") -> None:
    for bio_name in copied:
        path = user_dir / f"{bio_name}.yaml"
        try:
            if bio_name in previous:
                path.write_bytes(previous[bio_name])
            else:
                path.unlink()
        except OSError:
            pass
