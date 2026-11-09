"""tests.test_pack_setup_manifest -- `contributes.setup`, a pack's own Setup blocks (Halo 3.3.11.0 R3;
packs/manifest_setup.py, schemas/pack_yaml.py, pack.schema.json, field_help; docs/EXTENSION_API.md "Setup blocks"):

1. the fixture setup-blocks validates and installs; its blocks read back (a form over two of three schema keys, a
   check, a note), their keys are `pack:<id>:<block>`;
2. every bad value is one line naming the entry (an unknown kind, a field the schema does not have, a run outside the
   pack or missing, a check without its what / cost / time / writes, a note whose text file is missing or outside, an
   `after` that is not a core step, a key of another kind, ids) and install refuses it;
3. the YAML shape, the JSON schema twin and field_help carry the key; a pack without it is untouched.
Run: python -m tests.test_pack_setup_manifest
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome, fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
START, END = "contributes:\n  setup:\n", "config:\n"


def _lines(h, setup_block: str, *, config: "str | None" = None) -> list:
    from halo_harness.packs.discover import read_pack
    src = h.source("setup-blocks")
    text = (src / "pack.yaml").read_text(encoding="utf-8")
    head, rest = text.split(START, 1)
    _old, tail = rest.split(END, 1)
    text = head + "contributes:\n  setup:\n" + setup_block + (config if config is not None else END + tail)
    (src / "pack.yaml").write_text(text, encoding="utf-8")
    return read_pack(src, "source", folder_is_id=False).problems


@test
def test_the_fixture_validates_and_its_blocks_read_back(ctx: Ctx):
    from halo_harness.packs import manifest_setup as MS
    from halo_harness.packs.discover import find, read_pack
    pack = read_pack(fixture("setup-blocks"), "source")
    ctx.check(f"no problems, got {pack.problems}", pack.problems == [])
    blocks = MS.setup_of(pack.manifest)
    ctx.check(f"three blocks, one of each kind, got {[(b['id'], b['kind']) for b in blocks]}",
              [(b["id"], b["kind"]) for b in blocks] == [("prefs", "form"), ("reach", "check"), ("about", "note")])
    ctx.check("the form shows its two fields of the three schema keys",
              MS.form_fields(pack.manifest, blocks[0]) == ["style", "depth"] and MS.schema_keys(pack.manifest) == ["style", "depth", "extra"])
    ctx.check("a form without fields shows every key", MS.form_fields(pack.manifest, {"id": "x", "kind": "form"}) == ["style", "depth", "extra"])
    ctx.check("the form sits after the Default model step", blocks[0]["after"] == "model" and "after" not in blocks[1])
    ctx.check("its keys", MS.key_of("setup-blocks", "prefs") == "pack:setup-blocks:prefs"
              and MS.split_key("pack:setup-blocks:prefs") == ("setup-blocks", "prefs") and MS.split_key("team") == ("", ""))
    with PacksHome() as h:
        h.install(h.source("setup-blocks"))
        ctx.check("it installs", find("setup-blocks", cwd=h.repo) is not None)


@test
def test_every_bad_value_is_one_line_naming_the_entry(ctx: Ctx):
    bad = """    - {id: prefs, title: Prefs, kind: form, fields: [style, colour], after: summary}
    - {id: prefs, title: Again, kind: wizard}
    - {id: Bad--id, title: X, kind: note, text: setup/about.md}
    - {id: out, title: Out, kind: check, run: ["${halo_python}", "/etc/reach.py"], what: w, cost: c, time: t, writes: n}
    - {id: gone, title: Gone, kind: check, run: ["${halo_python}", "setup/missing.py"]}
    - {id: note1, title: Note, kind: note, text: setup/missing.md, run: ["${halo_python}", "setup/reach.py"]}
    - {id: note2, title: "", kind: note, text: ../outside.md}
    - {id: form2, title: Form, kind: form, text: setup/about.md}
"""
    with PacksHome() as h:
        got = _lines(h, bad)
        want = [
            "contributes.setup[1].id 'prefs' is used twice",
            "contributes.setup[2].id 'Bad--id' is not a block id (lower-case letters, digits, - and _, no --)",
            "contributes.setup[0].after 'summary' is not a core Setup step (one of providers, local, model, permissions, theme, team, linux, check)",
            "contributes.setup[0].fields: 'colour' is not a key of config.schema (style, depth, extra)",
            "contributes.setup[1].kind 'wizard' is not one of form, check, note",
            "contributes.setup[3].run: '/etc/reach.py' is outside the pack folder (a command in the pack: ${CLAUDE_PLUGIN_ROOT}/<path>)",
            "contributes.setup[4].run: setup/missing.py is not in the pack",
            "contributes.setup[4].what: required for a check (the line it shows before it runs)",
            "contributes.setup[4].writes: required for a check (the line it shows before it runs)",
            "contributes.setup[5].text: setup/missing.md is not in the pack",
            "contributes.setup[5].run: only a check block takes run (this one is a note)",
            "contributes.setup[6].title: required (the step's name in Setup's rail)",
            "contributes.setup[6].text: '../outside.md' is outside the pack folder (a file in the pack: setup/<name>.md)",
            "contributes.setup[7].text: only a note block takes text (this one is a form)",
        ]
        missing = [w for w in want if w not in got]
        ctx.check(f"each line, naming the entry; missing {missing}; got {got}", not missing)
        from halo_harness.packs.install import install
        ok, lines = install(str(h.sources / "setup-blocks"), cwd=h.repo)
        ctx.check(f"install refuses it with those lines, got {ok} {lines[:2]}", not ok and lines[0].startswith("setup-blocks: pack.yaml: "))
        got = _lines(h, "    - {id: p, title: P, kind: form}\n", config="")
        ctx.check(f"a form with no config.schema: one line, got {got}",
                  got == ["contributes.setup[0]: a form block shows config.schema's keys, and the pack has no config.schema"])
        got = _lines(h, "    - {id: p, title: P, kind: note, text: setup/about.md, colour: red}\n")
        ctx.check(f"an unknown key: the shape check's line, got {got}", any("colour" in ln for ln in got))
        got = _lines(h, "    oops\n")
        ctx.check(f"not a list: one line, got {got}", any(ln.startswith("contributes.setup") for ln in got))


@test
def test_the_shape_the_json_twin_and_field_help(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.packs import manifest_setup as MS
    from halo_harness.packs.discover import read_pack
    from halo_harness.schemas.pack_yaml import CONTRIBUTION_KEYS, SETUP_KEYS
    ctx.check("contributes has setup, then 3.3.12.0's themes", tuple(CONTRIBUTION_KEYS[CONTRIBUTION_KEYS.index("setup"):][:2]) == ("setup", "themes"))  # 3.3.13.0 R3: services after
    ctx.check("one key list in both modules", SETUP_KEYS == MS.SETUP_KEYS)
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "pack.schema.json").read_text(encoding="utf-8"))
    entry = schema["$defs"]["setup"]
    ctx.check("the JSON schema's contributes.setup is a list of $defs.setup",
              schema["properties"]["contributes"]["properties"]["setup"]["items"]["$ref"] == "#/$defs/setup")
    ctx.check("its $defs.setup holds the same keys, kinds and core steps", tuple(entry["properties"]) == SETUP_KEYS
              and entry["properties"]["kind"]["enum"] == list(MS.KINDS) and entry["properties"]["after"]["enum"] == list(MS.CORE_STEPS)
              and entry["required"] == ["id", "title", "kind"])
    ctx.check("field_help has a 3.3.11.0 line", "3.3.11.0" in field_help.PACK["contributes.setup"])
    plain = read_pack(fixture("doc-review"), "source")
    ctx.check(f"a pack without setup: no line, no blocks, got {plain.problems}", plain.problems == [] and MS.setup_of(plain.manifest) == []
              and MS.setup_lines(plain.manifest) == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
