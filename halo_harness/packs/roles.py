"""halo_harness.packs.roles -- a pack's bios and lineups as data (Halo
3.2.0.0 R2): what `halo pack inspect` and `halo pack doctor` list, and what
`halo agents list` / `halo teams list` and Studio's Roles group by pack.

A pack's bio is read from the pack's own files (never a file of yours that
shadows its name), `extends` followed inside the pack first; its model is
`bio_models.pick` over the catalog; its needs are `tools.needs`, each granted
or not. Works for an installed pack and for a source folder being inspected.

    pack_bios(pack, granted=..., cwd=..., state_dir=...)   # [{name, file, model, how, problem, capabilities, needs, namespace}]
    pack_lineups(pack)                                     # [{name, file, members, tiers, workflows, acceptance}]
    doctor_rows(pack, granted, ...)                        # one per unresolved capability set, one per ungranted need
    shadows(kind, cwd=..., state_dir=...)                  # {qualified name: (pack id, your file)}
    pack_groups(kind, cwd=..., state_dir=...)              # [(pack id, [qualified names])] for the active packs
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs import names as N


def _stems(folder: Path) -> "list[str]":
    try:
        return sorted(p.stem for p in folder.glob("*.yaml") if p.is_file() and N.is_valid_name(p.stem)
                      and not p.name.endswith(".team.yaml"))
    except OSError:
        return []


def _own(pack, ref, stems) -> str:
    """The pack's own stem `ref` names (bare or `<id>--<stem>`), else ''."""
    if not isinstance(ref, str) or not ref.strip():
        return ""
    owner, rest = N.unqualify(ref.strip())
    stem = rest if owner == pack.id else (ref.strip() if owner is None else "")
    return stem if stem in stems else ""


def _bio(pack, stem: str, stems, cwd, state_dir, chain=()) -> "tuple[dict, str]":
    """(the bio merged along `extends`, the `models.preference` the files name)."""
    from halo_harness.agents_yaml import BIO_SECTIONS, _merge_section, _read_yaml_file, resolve_agent_bio
    from halo_harness.packs.bio_models import chain_preference
    raw = _read_yaml_file(Path(pack.root) / "agents" / f"{stem}.yaml") or {}
    parent, written = {}, ""
    own = _own(pack, raw.get("extends"), stems)
    if own and own not in chain:
        parent, written = _bio(pack, own, stems, cwd, state_dir, chain + (stem,))
    elif isinstance(raw.get("extends"), str) and raw["extends"].strip() and not own:
        parent = resolve_agent_bio(raw["extends"].strip(), cwd=cwd, state_dir=state_dir) or {}
        written = chain_preference(raw["extends"].strip(), cwd=cwd, state_dir=state_dir)
    out = {s: _merge_section(parent.get(s), raw.get(s)) for s in BIO_SECTIONS}
    out.update({k: raw.get(k) for k in ("description", "kind", "tags") if k in raw})
    models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
    if isinstance(models.get("preference"), str) and models["preference"].strip():
        written = models["preference"].strip()
    return out, written


def pack_bios(pack, *, granted=(), cwd=None, state_dir=None, rows=None) -> "list[dict]":
    from halo_harness.packs import bio_models as BM
    from halo_harness.packs.bio_rules import bio_needs
    from halo_harness.packs.memory import bio_namespace
    stems = _stems(Path(pack.root) / "agents")
    have = set(granted or ())
    out = []
    for stem in stems:
        bio, written = _bio(pack, stem, stems, cwd, state_dir)
        models = {k: v for k, v in (bio.get("models") or {}).items() if k != "preference"}
        if written:
            models["preference"] = written
        info = BM.pick(models, rows=rows, state_dir=state_dir, cwd=cwd)
        model = info["ref"] if info else (written if written and written != "default" else "your default model")
        out.append({"name": N.qualify(pack.id, stem), "file": f"agents/{stem}.yaml", "model": model,
                    "how": info["how"] if info else ("preference" if written and written != "default" else "default"),
                    "problem": (info or {}).get("problem", ""), "capabilities": (info or {}).get("capabilities", []),
                    "line": BM.describe(info, model), "kind": str(bio.get("kind") or ""),
                    "needs": [{"need": n, "granted": n in have} for n in bio_needs(bio)],
                    "namespace": bio_namespace({**bio, "_pack": pack.id}) or ""})
    return out


def pack_lineups(pack) -> "list[dict]":
    from halo_harness.agents_yaml import _read_yaml_file
    bios = _stems(Path(pack.root) / "agents")
    out = []
    for stem in _stems(Path(pack.root) / "teams"):
        raw = _read_yaml_file(Path(pack.root) / "teams" / f"{stem}.yaml") or {}
        members = []
        for e in raw.get("agents") or []:
            if isinstance(e, dict) and isinstance(e.get("agent"), str):
                own = _own(pack, e["agent"], bios)
                members.append({"agent": N.qualify(pack.id, own) if own else e["agent"],
                                "role": str(e.get("as") or e.get("role") or "")})
        roles = raw.get("roles") if isinstance(raw.get("roles"), dict) else {}
        for role, value in roles.items():
            agent = value.get("agent") if isinstance(value, dict) else value
            if isinstance(agent, str):
                own = _own(pack, agent, bios)
                members.append({"agent": N.qualify(pack.id, own) if own else agent, "role": str(role)})
        acc = raw.get("acceptance") if isinstance(raw.get("acceptance"), dict) else {}
        out.append({"name": N.qualify(pack.id, stem), "file": f"teams/{stem}.yaml", "members": members,
                    "tiers": len(raw["tiers"]) if isinstance(raw.get("tiers"), list) else 0,
                    "workflows": [w for w in raw.get("workflows") or [] if isinstance(w, str)],
                    "acceptance": {k: acc[k] for k in ("test", "review") if k in acc}})
    return out


def doctor_rows(pack, granted, *, cwd=None, state_dir=None, rows=None) -> "list[dict]":
    """`{severity, check, text, fix, path}`: one per capability set no catalog model has, one per ungranted need."""
    bios = pack_bios(pack, granted=granted, cwd=cwd, state_dir=state_dir, rows=rows)
    sets: "dict[tuple, list[str]]" = {}
    needs: "dict[str, list[str]]" = {}
    for b in bios:
        if b["how"] == "default" and b["problem"]:
            sets.setdefault(tuple(b["capabilities"]), []).append(b["name"])
        for n in b["needs"]:
            if not n["granted"]:
                needs.setdefault(n["need"], []).append(b["name"])
    path = str(Path(pack.root) / "agents")
    out = []
    for caps, names in sets.items():
        who = f"bio {names[0]}: it runs" if len(names) == 1 else f"bios {', '.join(names)}: they run"
        out.append({"severity": "warns", "check": "bio-model", "path": path,
                    "text": f"{pack.id}: no model in the catalog has {', '.join(caps)} ({who} on your default model)",
                    "fix": "halo models --refresh, or Customize the bio in Studio's Roles and give it a model"})
    for need, names in sorted(needs.items()):
        who = f"bio {names[0]} uses" if len(names) == 1 else f"bios {', '.join(names)} use"
        out.append({"severity": "warns", "check": "bio-need", "path": path,
                    "text": f"{pack.id}: {who} {need}, which is not granted (the bio loads; what needs {need} "
                            "waits for your grant)",
                    "fix": f"halo pack enable {pack.id} --grant {need}"})
    return out


def card_warnings(bio, source: str, *, state_dir=None) -> "list[str]":
    """A Roles card's warnings for its bio: no catalog model has its tags (when the card runs on the bio's
    pick), and each need its pack has not been granted, with the command that grants it."""
    if not isinstance(bio, dict):
        return []
    from halo_harness.packs import state as S
    from halo_harness.packs.bio_rules import bio_needs
    out = []
    info = bio.get("_model") if isinstance(bio.get("_model"), dict) else {}
    if info.get("problem") and source in ("session", "capabilities", "bio"):
        out.append(f"bio {bio.get('name')}: {info['problem']}")
    pack_id = bio.get("_pack")
    if isinstance(pack_id, str) and pack_id:
        have = set(S.granted(pack_id, S.load(state_dir)))
        out += [f"bio {bio.get('name')} uses {n}, which is not granted: halo pack enable {pack_id} --grant {n}"
                for n in bio_needs(bio) if n not in have]
    return out


def _folders(kind: str, cwd, state_dir):
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    if kind == "bios":
        return [(A.project_agents_dir(cwd), "project"), (A.user_agents_dir(state_dir), "user")]
    return [(T.project_teams_dir(cwd), "project"), (T.user_teams_dir(state_dir), "user")]


def pack_groups(kind: str, *, cwd=None, state_dir=None) -> "list[tuple[str, list[str]]]":
    from halo_harness.packs.contribute import _active, folder_names
    sub = "agents" if kind == "bios" else "teams"
    return [(p.id, sorted(folder_names(Path(p.root) / sub, N.pack_source(p.id), skip=".team.yaml")))
            for p in _active(cwd, state_dir)]


def shadows(kind: str, *, cwd=None, state_dir=None) -> "dict[str, tuple[str, str]]":
    """Each active pack's name a file of yours (project or home) shadows: `{name: (pack id, your file)}`."""
    out: "dict[str, tuple[str, str]]" = {}
    for pack_id, names in pack_groups(kind, cwd=cwd, state_dir=state_dir):
        for name in names:
            for folder, _label in _folders(kind, cwd, state_dir):
                path = Path(folder) / f"{name}.yaml"
                if path.is_file() and name not in out:
                    out[name] = (pack_id, str(path))
    return out


def shadow_of(kind: str, name: str, source: str, *, cwd=None, state_dir=None) -> str:
    """The active pack whose `name` a file of yours (`source` project or user) shadows, else ''."""
    pack_id, stem = N.unqualify(name)
    if not pack_id or source not in ("project", "user"):
        return ""
    sub = "agents" if kind == "bios" else "teams"
    from halo_harness.packs.contribute import _active
    for p in _active(cwd, state_dir):
        if p.id == pack_id and (Path(p.root) / sub / f"{stem}.yaml").is_file():
            return p.id
    return ""


def list_lines(kind: str, names, *, cwd=None, state_dir=None) -> "list[str]":
    """`halo agents list` / `halo teams list`: your names (and the shipped ones) one per line as before, then
    one `pack <id>:` group per active pack, a name a file of yours shadows saying so. No pack: `names` alone."""
    groups = pack_groups(kind, cwd=cwd, state_dir=state_dir)
    shadowed = shadows(kind, cwd=cwd, state_dir=state_dir) if groups else {}
    offered = {n for _pid, ns in groups for n in ns}
    out = [n for n in names if n not in offered or n in shadowed]
    for pack_id, ns in groups:
        out.append(f"pack {pack_id}:")
        for n in ns:
            note = f"  shadowed by {shown_path(shadowed[n][1], cwd=cwd)}" if n in shadowed else ""
            out.append(f"  {n}{note}")
        if not ns:
            out.append("  (none)")
    return out


def shown_path(path: str, *, cwd=None) -> str:
    """`~/.halo/agents/x.yaml` or `.halo/agents/x.yaml`, as the lists print a file of yours."""
    from halo_harness.where.rows import display
    try:
        return display(path, cwd=cwd)
    except Exception:
        return path
