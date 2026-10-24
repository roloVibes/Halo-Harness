"""tests.test_packs_studio_contract -- a pack's `contributes.studio` (Halo
3.2.0.0 R3, schemas/pack_yaml.py studio(), packs/studio_rules.py,
packs/studio_registry.py): the fixtures validate clean and use every panel
kind; the JSON schema twin has the same keys; each failure fixture (an
unknown kind, a source outside the pack, a bundle without studio-script) is
one line naming the key and its pack.yaml line; the other meanings are one
line each; a bundle needs studio-script (enable and doctor name the grant);
the registry qualifies ids, resolves routes, adds the Settings form and its
palette entry, and leaves a disabled pack out.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW, FIXTURES, PacksHome, fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _good() -> dict:
    import yaml
    return yaml.safe_load((DOC_REVIEW / "pack.yaml").read_text(encoding="utf-8"))


def _lines(data, root=None) -> list:
    from halo_harness.packs.manifest import validate_manifest
    return [ln for ln in validate_manifest(data, root=root) if "studio" in ln]


@test
def test_the_fixtures_validate_and_use_every_kind(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.studio_rules import KINDS, panels_of
    kinds = set()
    for name in ("doc-review", "studio-bundle"):
        pack = read_pack(fixture(name), "source")
        ctx.check(f"{name} validates clean, got {pack.problems}", pack.problems == [])
        kinds |= {p.get("kind") for _k, _s, p in panels_of(pack.manifest)}
    ctx.check(f"the fixtures declare every kind but form (config_form adds it), got {sorted(kinds)}", kinds | {"form"} == set(KINDS))
    from halo_harness.schemas.pack_yaml import ANSWER_KEYS, PANEL_KEYS, SECTION_KEYS, STUDIO_KEYS
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "pack.schema.json").read_text(encoding="utf-8"))
    studio = schema["$defs"]["studio"]["properties"]
    ctx.check("the JSON twin's studio keys", tuple(studio) == STUDIO_KEYS)
    ctx.check("its panel keys", tuple(schema["$defs"]["panel"]["properties"]) == PANEL_KEYS)
    ctx.check("its section keys", tuple(studio["sections"]["items"]["properties"]) == SECTION_KEYS)
    ctx.check("its panel kinds", schema["$defs"]["panel"]["properties"]["kind"]["enum"] == list(KINDS))
    ctx.check("its answer keys", tuple(studio["attention"]["additionalProperties"]["properties"]["keys"]["properties"]) == ANSWER_KEYS)
    ctx.check("contributes.studio points at it", schema["properties"]["contributes"]["properties"]["studio"] == {"$ref": "#/$defs/studio"})
    ctx.check("studio-script is a permission name", "studio-script" in schema["properties"]["permissions"]["items"]["pattern"])


@test
def test_each_failure_fixture_is_one_line_with_its_line_number(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    for name, key, word, line in (("studio-bad-kind", "sections[0].panels[0].kind", "'chart' is not one of markdown", 12),
                                  ("studio-outside", "panels[0].source", "is outside the pack's folder", 9),
                                  ("studio-no-script", "sections[0].panels[0]", "needs the 'studio-script' permission", 12)):
        probs = read_pack(FIXTURES / name, "source").problems
        ctx.check(f"{name}: one line, got {probs}", len(probs) == 1)
        ctx.check(f"{name}: it names the key, the problem and pack.yaml line {line}, got {probs}",
                  bool(probs) and probs[0].startswith(f"pack.yaml line {line}: contributes.studio.{key}") and word in probs[0])


@test
def test_the_shape_names_the_closest_key(ctx: Ctx):
    data = _good()
    data["contributes"]["studio"]["palete"] = []
    data["contributes"]["studio"]["sections"][0]["panels"][0]["sorce"] = "x.md"
    lines = _lines(data)
    ctx.check(f"a typo in studio names 'palette', got {lines}", any("palete" in ln and "'palette'" in ln for ln in lines))
    ctx.check("a typo in a panel names 'source'", any("sorce" in ln and "'source'" in ln for ln in lines))
    data = _good()
    data["contributes"]["studio"]["events"]["review.done"]["lin"] = "x"
    ctx.check("inside an events mapping too", any("'line'" in ln for ln in _lines(data)))


def _one(mutate, word: str, ctx: Ctx, root=None) -> None:
    data = _good()
    mutate(data["contributes"]["studio"], data)
    lines = _lines(data, root)
    ctx.check(f"{word!r}: got {lines}", any(word in ln for ln in lines))


@test
def test_every_meaning_is_a_line(ctx: Ctx):
    sec = lambda st: st["sections"][0]  # noqa: E731
    cases = [
        (lambda st, d: sec(st).update(id="doc--x"), "is not an id"),
        (lambda st, d: sec(st)["panels"][1].update(id="notes"), "'notes' is used twice"),
        (lambda st, d: sec(st)["panels"][0].update(w=30), "w 30 is not 4..24"),
        (lambda st, d: sec(st)["panels"][0].update(h=2), "h 2 is not 8..200"),
        (lambda st, d: sec(st)["panels"][0].update(source="/etc/notes.md"), "is outside the pack's folder"),
        (lambda st, d: sec(st)["panels"][0].update(source="data:notes.md"), "is outside the pack's folder"),
        (lambda st, d: sec(st)["panels"][1].update(source="studio/checks.csv"), "a table panel's source is a .json file"),
        (lambda st, d: sec(st)["panels"][0].pop("source"), "required for a markdown panel"),
        (lambda st, d: sec(st)["panels"][0].update(columns=["a"]), "columns are a table panel's"),
        (lambda st, d: sec(st)["panels"][2].update(links=[]), "a links panel lists"),
        (lambda st, d: sec(st)["panels"][2]["links"].append({"label": "x", "url": "ftp://x"}), "is not an http(s) or mailto address"),
        (lambda st, d: sec(st)["panels"][2]["links"].append({"label": "x", "route": "docs/nowhere"}), "is not a route"),
        (lambda st, d: sec(st)["panels"][2]["links"].append({"label": "x"}), "a route or a url"),
        (lambda st, d: st["panels"][0].update(section="docs"), "is not a core section"),
        (lambda st, d: st["palette"][0].update(action="run:rm"), "is not route:<section>[/<panel>], url:<address> or config"),
        (lambda st, d: st["palette"][0].update(action="route:fleet/fleet-map"), "is not a route"),
        (lambda st, d: st["events"].update({"review.started": {"line": "x"}}), "not one of contributes.events"),
        (lambda st, d: st["events"]["review.done"].pop("line"), "line: required"),
        (lambda st, d: st["attention"]["review.ask"].update(keys={}), "name the row's answers"),
        (lambda st, d: st["attention"].update({"Bad Kind": {"label": "x", "keys": {"a": "ok"}}}), "not a row kind"),
        (lambda st, d: d.pop("config"), "has no config.schema"),
        (lambda st, d: (st.pop("sections"), st["palette"].pop()), "declare a section under sections:"),
        (lambda st, d: (st.update(config_form=False), st["palette"].append({"id": "s", "label": "S", "action": "config"})), "config opens the settings form"),
        (lambda st, d: d["contributes"].pop("events"), "contributes.events declares none"),
    ]
    for mutate, word in cases:
        _one(mutate, word, ctx)
    _one(lambda st, d: sec(st)["panels"][0].update(source="studio/missing.md"), "studio/missing.md is not in the pack", ctx, DOC_REVIEW)
    data = _good()
    data["contributes"]["studio"]["sections"][0]["panels"][1]["source"] = "data:checks.json"
    ctx.check("a table may read data:<path> in the pack's data folder", _lines(data, DOC_REVIEW) == [])


@test
def test_a_bundle_needs_studio_script_and_enable_names_the_grant(ctx: Ctx):
    from halo_harness.packs.manifest import needed
    raw = json.loads(json.dumps(__import__("yaml").safe_load((FIXTURES / "studio-bundle" / "pack.yaml").read_text(encoding="utf-8"))))
    ctx.check("the bundle panel needs studio-script", ("studio-script", "Studio panel greet (a bundle)") in needed(raw, None))
    with PacksHome() as h:
        h.install(h.source("studio-bundle"))
        code, out, _err = h.cli("enable", "studio-bundle")
        ctx.check(f"enable lists the request and the grant command, got {out!r}", code == 0
                  and "studio-script (Studio panel greet (a bundle)): not granted" in out
                  and "halo pack enable studio-bundle --grant studio-script" in out)
        code, out, _err = h.cli("doctor")
        ctx.check(f"doctor names it too, got {out!r}", "studio-script" in out)
        code, out, _err = h.cli("enable", "studio-bundle", "--grant", "studio-script")
        ctx.check("granted", code == 0 and "studio-script (Studio panel greet (a bundle)): granted" in out)


@test
def test_the_registry_qualifies_resolves_and_leaves_disabled_packs_out(ctx: Ctx):
    from halo_harness.packs.studio_registry import registry
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["hooks"])
        h.install(h.source("studio-bundle"), enable=True)
        reg = registry(cwd=h.repo)
        by = {p["id"]: p for p in reg["packs"]}
        ctx.check(f"both packs, in order, got {list(by)}", list(by) == ["doc-review", "studio-bundle"] and reg["core"][0] == "session")
        doc = by["doc-review"]
        sec = doc["sections"][0]
        ctx.check("the section id is qualified, its title as written", sec["id"] == "doc-review--docs" and sec["title"] == "Docs review")
        ids = [p["id"] for p in sec["panels"]]
        ctx.check(f"its panels, then Settings (config_form), got {ids}", ids == ["doc-review--notes", "doc-review--checks", "doc-review--links",
                                                                         "doc-review--report", "doc-review--settings"])  # report: 3.2.0.0 R5
        notes = sec["panels"][0]
        ctx.check(f"a panel's file path, help and source line, got {notes}", notes["file"] == "api/pack/doc-review/file/studio/notes.md"
                  and notes["about"] == "from pack doc-review" and notes["help"].startswith("The reviewer's notes") and notes["collapsed"] is False)
        links = sec["panels"][2]["links"]
        ctx.check(f"routes resolved, a url kept, got {links}", links[0]["route"] == {"section": "roles"}
                  and links[1]["route"] == {"section": "doc-review--docs", "panel": "doc-review--checks"} and links[2]["url"].startswith("https://"))
        core = doc["panels"][0]
        ctx.check(f"the Session panel: core section, collapsed, got {core}", core["section"] == "session" and core["collapsed"] is True
                  and core["id"] == "doc-review--reviews" and core["kind"] == "events")
        acts = [(e["label"], e["group"], e["action"]) for e in doc["palette"]]
        ctx.check(f"the palette: the action, then Settings, got {acts}",
                  acts == [("Open the review checks", "pack doc-review", {"kind": "route", "section": "doc-review--docs", "panel": "doc-review--checks"}),
                           ("Settings: Documentation Review", "pack doc-review", {"kind": "route", "section": "doc-review--docs", "panel": "doc-review--settings"})])
        ctx.check("events and attention carried (3.2.0.0 R5: + the kind schema's view)",
                  doc["events"] == {"review.done": {"label": "REVIEW", "line": "{file}: {findings} findings", "view": "keyvalue"}}
                  and doc["attention"]["review.ask"]["keys"] == {"a": "accept", "r": "redo", "s": "skip", "o": "open"})
        bundle = by["studio-bundle"]["sections"][0]["panels"][0]
        ctx.check(f"a bundle not granted: no file, the grant line, got {bundle}", bundle["script"] == "not granted" and "file" not in bundle
                  and bundle["grant"] == "halo pack enable studio-bundle --grant studio-script" and by["studio-bundle"]["script"] == "not granted")
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import disable, enable
        enable(find("studio-bundle", cwd=h.repo), grant=["studio-script"])
        bundle = registry(cwd=h.repo)["packs"][1]["sections"][0]["panels"][0]
        ctx.check("granted: the module's path", bundle["script"] == "granted" and bundle["file"] == "api/pack/studio-bundle/file/studio/hello.js")
        disable("doc-review")
        ctx.check("a disabled pack is not in it", [p["id"] for p in registry(cwd=h.repo)["packs"]] == ["studio-bundle"])
        h.install(h.source("rare-caps"), enable=True)
        ctx.check("a running pack without contributes.studio adds nothing", [p["id"] for p in registry(cwd=h.repo)["packs"]] == ["studio-bundle"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
