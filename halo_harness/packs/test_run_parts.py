"""halo_harness.packs.test_run_parts -- `halo pack test`'s checks that start no process (Halo 3.3.12.0 R4): each bio
and lineup loads, each skill and command parses, each event and artifact schema validates its sample, each workflow
compiles, each Studio panel's source is there (a bundle module exports `mount`), the bundle block, the fleet
capabilities, a mode switch read back, a theme's contrast pins, the tools `requires:` names. `r` is test_run.Run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SAMPLES = "tests/samples"


def _contributes(r) -> dict:
    c = r.manifest.get("contributes")
    return c if isinstance(c, dict) else {}


def agents(r) -> None:
    from halo_harness import agents_yaml as A
    for rel in _contributes(r).get("agents") or [] if r.wants("agents") else []:
        if not str(rel).endswith(".yaml"):
            from halo_harness.config.frontmatter import parse
            fm, _ = parse((r.root / rel).read_text(encoding="utf-8"))
            r.add("agents", rel, "the plugin agent's frontmatter has a name and a description",
                  isinstance(fm, dict) and bool(fm.get("name")) and bool(fm.get("description")), "add name: and description:")
            continue
        name = f"{r.pack.id}--{Path(rel).stem}"
        bio = A.resolve_agent_bio(name, cwd=r.project)
        problems = A.validate_agent_bio(A.load_agent_bio_raw(name, cwd=r.project) or {}, name=name, cwd=r.project)
        r.add("agents", rel, f"bio {name} loads", bio is not None and not problems, "; ".join(problems) or "it does not load")


def teams(r) -> None:
    from halo_harness import teams_yaml as T
    for rel in _contributes(r).get("teams") or [] if r.wants("teams") else []:
        name = f"{r.pack.id}--{Path(rel).stem}"
        lineup = T.resolve_team_template(name, cwd=r.project)
        problems = T.validate_team_template(lineup or {}, name=name, cwd=r.project) if lineup else ["it does not load"]
        r.add("teams", rel, f"lineup {name} loads and every bio it names resolves", not problems, "; ".join(problems))


def skills(r) -> None:
    if not r.wants("skills") or not (r.root / "skills").is_dir():
        return
    from halo_harness.commands.skills import discover_all_skills
    found = discover_all_skills(r.project, home=r.home, plugin_roots=[r.root])
    for md in sorted((r.root / "skills").glob("*/SKILL.md")):
        name = f"{r.pack.id}:{md.parent.name}"
        r.add("skills", md.relative_to(r.root).as_posix(), f"skill {name} parses and is offered", name in found,
              "the frontmatter needs name: and description:, the folder is skills/<name>/SKILL.md")


def commands(r) -> None:
    if not r.wants("commands") or not (r.root / "commands").is_dir():
        return
    from halo_harness.commands.registry import Registry
    from halo_harness.config.frontmatter import parse
    reg = Registry.discover(r.project, home=r.home, plugin_roots=[r.root])
    for md in sorted((r.root / "commands").rglob("*.md")):
        rel = md.relative_to(r.root).as_posix()
        fm, body = parse(md.read_text(encoding="utf-8"))
        name = f"{r.pack.id}:" + ":".join(md.relative_to(r.root / "commands").with_suffix("").parts)
        ok = isinstance(fm, dict) and bool(str(body or "").strip()) and reg.resolve(name) is not None
        r.add("commands", rel, f"/{name} parses and is offered", ok, "a frontmatter (--- description: ... ---) and a body")


def _sample(r, kind: str, name: str):
    path = r.root / SAMPLES / kind / f"{name}.json"
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return path, None


def _schemas(r, kind: str, names, schema_of) -> None:
    from halo_harness.packs.typed import check
    for name in names:
        schema, (path, sample) = schema_of(name), _sample(r, kind, name)
        rel = f"{SAMPLES}/{kind}/{name}.json"
        if schema is None:
            r.add(kind, f"{kind}/{name}.json", f"{name} has no schema; nothing to check", None)
        elif sample is None:
            r.add(kind, rel, f"no sample for {name}; its schema is not exercised", None,
                  f"add {rel}: one document the schema takes")
        else:
            lines = check(sample, schema)
            r.add(kind, rel, f"the {kind[:-1]} sample fits {name}'s schema", not lines, "; ".join(lines))


def events(r) -> None:
    from halo_harness.packs.typed import event_kinds, event_schema
    if r.wants("events"):
        _schemas(r, "events", event_kinds(r.manifest), lambda k: event_schema(r.root, r.manifest, k))


def artifacts(r) -> None:
    from halo_harness.packs.typed import artifact_names, artifact_schema
    if r.wants("artifacts"):
        _schemas(r, "artifacts", artifact_names(r.manifest), lambda n: artifact_schema(r.root, n))


def _inputs(r, wf) -> dict:
    from halo_harness.workflows import spec
    out = {}
    for name, sp in spec.inputs(wf).items():
        if sp.get("default") is not None or not sp.get("required"):
            continue
        kind = str(sp.get("type") or "text")
        if kind == "path":
            (r.project / "sample").mkdir(exist_ok=True)
            (r.project / "sample" / "one.md").write_text("# One\n\nA sample file.\n", encoding="utf-8")
            out[name] = "sample"
        else:
            out[name] = "{}" if kind == "json" else "a sample request"
    return out


def workflows(r) -> None:
    from halo_harness.packs.bio_rules import declared_workflows
    from halo_harness.workflows import compile as C
    from halo_harness.workflows import inputs as I
    from halo_harness.workflows import spec
    for name in declared_workflows(r.manifest) if r.wants("workflows") else []:
        rel = f"workflows/{name}.yaml"
        wf, why = spec.find(f"{r.pack.id}/{name}", cwd=r.project)
        if wf is None:
            r.add("workflows", rel, f"workflow {name} loads", False, why)
            continue
        here: list = []
        saved = (I.prerequisites, I.capability_problems)
        I.prerequisites = lambda *a, **k: here.extend(saved[0](*a, **k)) or []
        I.capability_problems = lambda *a, **k: here.extend(saved[1](*a, **k)) or []
        try:
            done = C.compile_workflow(wf, _inputs(r, wf), repo=r.project, cwd=r.project)
        finally:
            I.prerequisites, I.capability_problems = saved
        r.add("workflows", rel, f"workflow {r.pack.id}/{name} compiles to an Orchestra goal ({len(done.jobs)} jobs)",
              not done.problems, "; ".join(done.problems))
        for line in dict.fromkeys(here):
            r.add("workflows", rel, f"needs on the machine that runs it: {line}", None)


def studio(r) -> None:
    from halo_harness.packs import studio_rules as R
    for section, _x, p in R.panels_of(r.manifest) if r.wants("studio") else []:
        kind, src = p.get("kind"), p.get("source")
        if kind not in R.NEED_SOURCE or not isinstance(src, str) or (kind == "artifact" and src == R.LATEST):
            continue
        if src.startswith(R.DATA_PREFIX):
            r.add("studio", "pack.yaml", f"panel {p.get('id')}: {src} is read from the data folder when it is there",
                  src.lower().endswith(R.SUFFIXES[kind]), f"a {kind} panel reads a {' or '.join(R.SUFFIXES[kind])} file")
            continue
        path = r.root / src
        ok = path.is_file() and path.suffix.lower() in R.SUFFIXES[kind]
        r.add("studio", src, f"panel {p.get('id')} ({kind}) has its source", ok, "the file is in the pack, of that type")
        if ok and kind == "bundle":
            from halo_harness.packs.test_run_proc import es_module_lines
            lines = es_module_lines(path, r.timeout)
            r.add("studio", src, "the bundle module is an ES module that exports mount(el, api)", not lines,
                  "; ".join(lines))


def bundle(r) -> None:
    from halo_harness.packs.manifest_bundle import block, bundle_lines
    b = block(r.manifest) if r.wants("bundle") else None
    if b is None:
        return
    lines = bundle_lines(r.manifest)
    r.add("bundle", "pack.yaml", "the bundle: block reads clean against the bundle schema", not lines, "; ".join(lines))
    card, reserve = 24.0, 2.0  # the fake card: 24 GB, the per-card reserve kept free
    res = b.get("reservation") or {}
    gb = res.get("vram_gb")
    if not isinstance(gb, (int, float)):
        r.add("bundle", "pack.yaml", "the reservation names no vram_gb: its size is the real verdict's to work out", None,
              f"halo pack verdict {r.pack.id} judges it against your card")
    else:
        r.add("bundle", "pack.yaml", f"the reservation ({gb:g} GB) fits a fake {card:g} GB card with {reserve:g} GB kept "
              "free", gb <= card - reserve, f"halo pack verdict {r.pack.id} judges it against your own card")


def fleet(r) -> None:
    from halo_harness.packs.fleet_rules import capabilities_of
    caps = capabilities_of(r.manifest) if r.wants("fleet") else []
    top = set(r.manifest.get("capabilities") or [])
    for c in caps:
        r.add("fleet", "pack.yaml", f"fleet capability {c.get('name')} is one of the pack's capabilities",
              c.get("name") in top, "list it under the top-level capabilities:")


def modes(r) -> None:
    from halo_harness.packs import mode_state as M
    from halo_harness.packs.manifest_policy import modes_of
    for e in modes_of(r.manifest) if r.wants("modes") or r.wants("policy") else []:
        mid = str(e.get("id"))
        ok, lines = M.set_mode(r.pack.id, mid, True, by="test", cwd=r.project)
        on = M.read(r.pack.id).get("mode") == mid
        ok2, _ = M.set_mode(r.pack.id, mid, False, by="test", cwd=r.project)
        r.add("modes", "pack.yaml", f"mode {mid} turns on and off, read back from mode.json",
              ok and on and ok2 and not M.read(r.pack.id).get("mode"), "; ".join(lines))


def themes(r) -> None:
    from halo_harness.themes.registry import PAIRS, contrast
    for e in _contributes(r).get("themes") or [] if r.wants("themes") else []:
        pal = e.get("palette") if isinstance(e, dict) and isinstance(e.get("palette"), dict) else {}
        low = [f"{fg} on {bg} {contrast(pal[fg], pal[bg]):.2f}:1 < {floor}:1" for fg, bg, floor in PAIRS
               if isinstance(pal.get(fg), str) and isinstance(pal.get(bg), str)
               and re.match(r"^#[0-9a-fA-F]{6}$", pal[fg]) and re.match(r"^#[0-9a-fA-F]{6}$", pal[bg])
               and contrast(pal[fg], pal[bg]) < floor]
        r.add("themes", "pack.yaml", f"theme {e.get('id')} meets the contrast pins the ten palettes meet", not low,
              "; ".join(low))


def requirements(r) -> None:
    from halo_harness.packs.manifest_requires import install_line, present, tools_of
    for e in tools_of(r.manifest) if r.wants("integration") else []:
        ok, why = present(e)
        used = ", ".join(map(str, e.get("used_by") or [])) or "the parts that use it"
        if ok:
            r.add("integration", "pack.yaml", f"{e.get('name')} ({e.get('kind')}) is here: {why}", True)
        else:
            r.add("integration", "pack.yaml", f"{why}: {used} skipped", None,
                  f"install it: {install_line(e) or e.get('url')}, then halo pack test again")
