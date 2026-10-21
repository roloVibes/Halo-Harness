"""tests.test_packs_manifest -- a pack's pack.yaml (Halo 3.2.0.0 R1,
halo_harness/packs/manifest.py): the fixture pack validates clean; a file
that is not YAML, an unknown key (named with the closest known one), a bad
semver, a bad `halo_api` range, a missing required key, a bad id, a
permission name nothing knows, a contribution path outside the plugin
layout, a contribution whose permission the pack does not request, and a
plugin.json naming another plugin are each one line; the JSON schema twin
lists the same keys as the Python shape; "pack" is a schema kind.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _good() -> dict:
    import yaml
    return yaml.safe_load((DOC_REVIEW / "pack.yaml").read_text(encoding="utf-8"))


def _lines(data, root=None) -> list:
    from halo_harness.packs.manifest import validate_manifest
    return validate_manifest(data, root=root)


@test
def test_the_fixture_pack_is_valid(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    pack = read_pack(DOC_REVIEW, "source")
    ctx.check(f"doc-review validates clean, got {pack.problems}", pack.problems == [])
    ctx.check("id, name and version are read", (pack.id, pack.name, pack.version) == ("doc-review", "Documentation review", "1.0.0"))
    from halo_harness.schemas import KINDS
    ctx.check("the schema kind is registered", "pack" in KINDS)


@test
def test_malformed_yaml_and_a_missing_file(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    d = Path(tempfile.mkdtemp(prefix="pack-bad-"))
    try:
        missing = read_pack(d, "source")
        ctx.check(f"no pack.yaml: one line, got {missing.problems}", len(missing.problems) == 1 and "no pack.yaml" in missing.problems[0])
        (d / "pack.yaml").write_text("id: [unclosed\n", encoding="utf-8")
        bad = read_pack(d, "source")
        ctx.check(f"not YAML: one line, got {bad.problems}", len(bad.problems) == 1 and "YAML mapping" in bad.problems[0])
        (d / "pack.yaml").write_text("- a list\n", encoding="utf-8")
        ctx.check("a list, not a mapping: one line", len(read_pack(d, "source").problems) == 1)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test
def test_an_unknown_key_names_the_closest_one(ctx: Ctx):
    data = _good()
    data["permisions"] = ["hooks"]
    data["contributes"]["skils"] = "skills"
    lines = _lines(data)
    top = [ln for ln in lines if "permisions" in ln]
    ctx.check(f"the top-level typo is one line naming 'permissions', got {top}", len(top) == 1 and "'permissions'" in top[0])
    inner = [ln for ln in lines if "skils" in ln]
    ctx.check(f"a typo inside contributes too, got {inner}", len(inner) == 1 and "'skills'" in inner[0])


@test
def test_bad_semver_and_bad_ranges(ctx: Ctx):
    data = _good()
    data["version"] = "1.0"
    ctx.check("version 1.0 is not semver", any("not semver" in ln for ln in _lines(data)))
    for bad, word in (({"min": "2.0", "max": "1.0"}, "above"), ({"min": "one"}, "not a version"),
                      ({"max": "1.9"}, "halo_api.min: required"), ({"min": "1.0", "upto": "2"}, "takes min and max")):
        data = _good()
        data["halo_api"] = bad
        lines = _lines(data)
        ctx.check(f"halo_api {bad}: a line with {word!r}, got {lines}", any(word in ln for ln in lines))
    data = _good()
    data["halo"] = {"min": "3.x"}
    ctx.check("a bad halo range is a line", any(ln.startswith("halo.min") for ln in _lines(data)))
    from halo_harness.packs import semver as V
    ctx.check("semver: a pre-release sorts first", V.compare("1.0.0-rc.1", "1.0.0") == -1)
    ctx.check("release numbers compare across lengths", V.compare("3.2.0.0", "3.2") == 0 and V.compare("1.10", "1.9") == 1)
    ctx.check("max is inclusive at its precision", V.in_range("1.9.4", {"max": "1.9"}) and not V.in_range("2.0", {"max": "1.9"}))


@test
def test_required_keys_id_rule_and_names(ctx: Ctx):
    data = _good()
    for key in ("id", "name", "version", "halo_api"):
        data.pop(key)
    lines = _lines(data)
    for key in ("id", "name", "version", "halo_api"):
        ctx.check(f"{key}: required", f"{key}: required" in lines)
    for bad in ("Doc", "doc--review", "doc-", "1doc"):
        data = _good()
        data["id"] = bad
        ctx.check(f"id {bad!r} is one line", sum("not a pack id" in ln for ln in _lines(data)) == 1)
    data = _good()
    data["permissions"] = ["mcp:lint", "hooks", "root"]
    data["capabilities"] = ["Docs Review"]
    lines = _lines(data)
    ctx.check("an unknown permission name", any("'root' is not one of" in ln for ln in lines))
    ctx.check("a bad capability name", any("capabilities:" in ln for ln in lines))
    data = _good()
    data["requires"] = [{"pack": "doc-review"}, {"pack": "base", "version": "x"}]
    lines = _lines(data)
    ctx.check("a pack does not require itself", any("does not require itself" in ln for ln in lines))
    ctx.check("a bad requires version", any("requires[1].version" in ln for ln in lines))
    data = _good()
    data["migrations"] = [{"from": "1.0.0", "to": "1.1.0"}]
    ctx.check("a migration needs its note", any("migrations[0].note: required" in ln for ln in _lines(data)))


@test
def test_files_permissions_and_plugin_name_against_the_folder(ctx: Ctx):
    d = Path(tempfile.mkdtemp(prefix="pack-files-")) / "doc-review"
    shutil.copytree(DOC_REVIEW, d)
    try:
        data = _good()
        data["contributes"]["agents"] = ["agents/reviewer.yaml", "bios/other.yaml", "agents/missing.yaml"]
        data["contributes"]["skills"] = "my-skills"
        lines = _lines(data, d)
        ctx.check(f"a path outside agents/ is a line, got {lines}", any("'bios/other.yaml' is not agents/" in ln for ln in lines))
        ctx.check("a listed file that is not there", any("agents/missing.yaml is not in the pack" in ln for ln in lines))
        ctx.check("skills live at skills (the plugin layout)", any("a pack's skills live at skills" in ln for ln in lines))
        data = _good()
        data["permissions"] = ["hooks"]
        lines = _lines(data, d)
        ctx.check(f"the MCP server needs mcp:lint, which is not requested, got {lines}",
                  any("MCP server lint needs 'mcp:lint'" in ln for ln in lines))
        data = _good()
        data["permissions"] = ["mcp:lint", "mcp:other", "hooks"]
        ctx.check("mcp:<server> names a declared server", any("'mcp:other'" in ln for ln in _lines(data, d)))
        (d / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "other"}), encoding="utf-8")
        ctx.check("plugin.json names the pack's id", any("plugin.json names the plugin 'other'" in ln for ln in _lines(_good(), d)))
        from halo_harness.packs.manifest import validate_manifest
        moved = d.parent / "renamed"
        d.rename(moved)
        ctx.check("an installed pack's folder is its id",
                  any("a pack's folder is named by its id" in ln for ln in validate_manifest(_good(), root=moved, folder_is_id=True)))
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)


@test
def test_the_json_schema_lists_the_same_keys(ctx: Ctx):
    from halo_harness.packs.manifest import PERMISSIONS, REQUIRED
    from halo_harness.schemas.pack_yaml import CONTRIBUTION_KEYS, TOP_KEYS
    path = Path(__file__).resolve().parent.parent / "halo_harness" / "packs" / "schema" / "pack.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    ctx.check("top-level keys match", tuple(schema["properties"]) == TOP_KEYS)
    ctx.check("contributes keys match", tuple(schema["properties"]["contributes"]["properties"]) == CONTRIBUTION_KEYS)
    ctx.check("strict at the top and required keys match", schema["additionalProperties"] is False
              and tuple(schema["required"]) == REQUIRED)
    pattern = schema["properties"]["permissions"]["items"]["pattern"]
    ctx.check("the permission names match", all(p in pattern for p in PERMISSIONS))
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("the schema ships as package data", '"packs/schema/*.json"' in pyproject)
    from halo_harness import field_help
    keys = [k for k in TOP_KEYS if k not in ("contributes", "config")] + [f"contributes.{k}" for k in CONTRIBUTION_KEYS]         + ["config.schema", "config.defaults"]
    missing = [k for k in keys if not field_help.PACK.get(k)]
    ctx.check(f"field_help has a line for every manifest key; missing {missing}", not missing and set(field_help.PACK) == set(keys))
    ctx.check("GET /api/field-help carries them", field_help.as_json()["pack"] == field_help.PACK)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
