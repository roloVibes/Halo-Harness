"""tests.test_pack_themes_manifest -- `contributes.themes`, a pack's own palettes (Halo 3.3.12.0 R2;
packs/manifest_themes.py, schemas/pack_yaml.py, pack.schema.json, field_help; docs/EXTENSION_API.md "Themes"):

1. the fixture pack-theme validates and installs; its two palettes read back as `pack-theme/nightshade` (dark) and
   `pack-theme/linen` (light) with every token, and every pinned pair of both (and their -daltonized variants) meets
   the floor the ten meet;
2. every bad value is one line naming the entry (an id that is not `[a-z][a-z0-9-]*`, a core palette's id, an id
   ending in a modifier, an id used twice, a missing and an extra token, a value that is not #rrggbb, a posture
   outside the two, a label left out, a text-on-surface pair under WCAG AA) and install refuses it;
3. the YAML shape, the JSON schema twin and field_help carry the key; a pack without it is untouched.
Run: python -m tests.test_pack_themes_manifest
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
HEAD = "contributes:\n  themes:\n"


def _night(**over) -> dict:
    from halo_harness.packs.discover import read_pack
    pal = dict(read_pack(fixture("pack-theme"), "source").manifest["contributes"]["themes"][0]["palette"])
    pal.update(over)
    return pal


def _flow(entry: dict) -> str:
    return "    - " + json.dumps(entry) + "\n"


def _lines(h, entries: list) -> list:
    from halo_harness.packs.discover import read_pack
    src = h.source("pack-theme")
    text = (src / "pack.yaml").read_text(encoding="utf-8")
    head = text.split(HEAD, 1)[0]
    (src / "pack.yaml").write_text(head + HEAD + "".join(_flow(e) for e in entries), encoding="utf-8")
    return read_pack(src, "source", folder_is_id=False).problems


@test
def test_the_fixture_validates_and_its_palettes_read_back(ctx: Ctx):
    from halo_harness.packs import manifest_themes as MT
    from halo_harness.packs.discover import find, read_pack
    from halo_harness.themes import registry
    from halo_harness.themes.palettes import TOKEN_NAMES
    pack = read_pack(fixture("pack-theme"), "source")
    ctx.check(f"no problems, got {pack.problems}", pack.problems == [])
    pals = MT.palettes("pack-theme", pack.manifest)
    ctx.check(f"two palettes, got {[(p['id'], p['posture']) for p in pals]}",
              [(p["id"], p["posture"]) for p in pals] == [("pack-theme/nightshade", "dark"), ("pack-theme/linen", "light")])
    ctx.check("each with every token, lower-case #rrggbb", all(tuple(p["tokens"]) == TOKEN_NAMES and all(
        v.startswith("#") and v == v.lower() and len(v) == 7 for v in p["tokens"].values()) for p in pals))
    ctx.check("its name", MT.theme_name("pack-theme", "linen") == "pack-theme/linen" and pals[1]["local_id"] == "linen")
    for p in pals:
        for variant in (p["tokens"], registry.daltonize(p["tokens"], p["posture"])):
            low = [(fg, bg, round(registry.contrast(variant[fg], variant[bg]), 2)) for fg, bg, floor in registry.PAIRS
                   if registry.contrast(variant[fg], variant[bg]) < floor]
            ctx.check(f"{p['id']}: every pinned pair at its floor, got {low}", low == [])
    with PacksHome() as h:
        h.install(h.source("pack-theme"))
        ctx.check("it installs", find("pack-theme", cwd=h.repo) is not None)


@test
def test_every_bad_value_is_one_line_naming_the_entry(ctx: Ctx):
    night = _night()
    no_bad = {k: v for k, v in night.items() if k != "bad"}
    entries = [
        {"id": "Night_Shade", "label": "L", "posture": "dark", "palette": night},
        {"id": "holo", "label": "L", "posture": "dark", "palette": night},
        {"id": "dim-ansi", "label": "L", "posture": "dark", "palette": night},
        {"id": "twice", "label": "L", "posture": "dark", "palette": night},
        {"id": "twice", "label": "L", "posture": "dark", "palette": night},
        {"id": "gaps", "label": "L", "posture": "dark", "palette": {**no_bad, "glow": "#ffffff"}},
        {"id": "hexes", "label": "L", "posture": "dark", "palette": {**night, "ok": "green", "warn": "#ffd27"}},
        {"id": "sideways", "label": "L", "posture": "dim", "palette": night},
        {"id": "nolabel", "posture": "dark", "palette": night},
        {"id": "murky", "label": "L", "posture": "dark", "palette": {**night, "text": "#3d3654"}},
    ]
    with PacksHome() as h:
        got = _lines(h, entries)
        want = [
            "contributes.themes[0].id 'Night_Shade' is not a palette id (lower-case letters, digits and -, a letter first)",
            "contributes.themes[1].id 'holo' is a core palette's id; pick another (the ten: claude-dark, claude-light, dawn, "
            "dusk, ember, forest, holo, midnight, paper, slate)",
            "contributes.themes[2].id 'dim-ansi' ends in a modifier (-daltonized, -ansi); pick another",
            "contributes.themes[4].id 'twice' is used twice",
            "contributes.themes[5].palette: missing bad (a palette names every token)",
            "contributes.themes[5].palette: glow is not a token (the tokens: bg, bg2, surface, surface2, border, line, text, "
            "muted, faint, accent, accent2, accent_ink, ok, warn, bad, user, tool)",
            "contributes.themes[6].palette.ok: 'green' is not a #rrggbb colour",
            "contributes.themes[6].palette.warn: '#ffd27' is not a #rrggbb colour",
            "contributes.themes[7].posture 'dim' is not one of dark, light",
            "contributes.themes[8].label: required (the line a person reads beside the palette)",
        ]
        missing = [w for w in want if w not in got]
        ctx.check(f"each line, naming the entry; missing {missing}; got {got}", not missing)
        murky = [ln for ln in got if ln.startswith("contributes.themes[9].palette: text on ")]
        ctx.check(f"a text-on-surface pair under AA: one line per pair with its ratio, got {murky}",
                  len(murky) >= 4 and any("text on surface reads" in ln and "under WCAG AA's 4.5:1 (#3d3654 on #171325)" in ln
                                          for ln in murky))
        ctx.check("a good entry says nothing", not [ln for ln in got if ln.startswith("contributes.themes[3]")])
        from halo_harness.packs.install import install
        ok, lines = install(str(h.sources / "pack-theme"), cwd=h.repo)
        ctx.check(f"install refuses it with those lines, got {ok} {lines[:2]}", not ok and lines[0].startswith("pack-theme: pack.yaml: "))
        src = h.source("pack-theme")
        text = (src / "pack.yaml").read_text(encoding="utf-8").split(HEAD, 1)[0]
        (src / "pack.yaml").write_text(text + "contributes:\n  themes: oops\n", encoding="utf-8")
        from halo_harness.packs.discover import read_pack
        got = read_pack(src, "source", folder_is_id=False).problems
        ctx.check(f"not a list: one line, got {got}", any(ln.startswith("contributes.themes") for ln in got))
        got = _lines(h, [{"id": "x", "label": "L", "posture": "dark", "palette": night, "colour": "red"}])
        ctx.check(f"an unknown key: the shape check's line, got {got}", any("colour" in ln for ln in got))


@test
def test_the_shape_the_json_twin_and_field_help(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.packs import manifest_themes as MT
    from halo_harness.packs.discover import read_pack
    from halo_harness.schemas.pack_yaml import CONTRIBUTION_KEYS, THEME_KEYS
    from halo_harness.themes.palettes import TOKEN_NAMES
    ctx.check("contributes has themes, last", CONTRIBUTION_KEYS[-1] == "themes")
    ctx.check("one key list in both modules", THEME_KEYS == MT.THEME_KEYS)
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "pack.schema.json").read_text(encoding="utf-8"))
    entry = schema["$defs"]["theme"]
    ctx.check("the JSON schema's contributes.themes is a list of $defs.theme",
              schema["properties"]["contributes"]["properties"]["themes"]["items"]["$ref"] == "#/$defs/theme")
    ctx.check("its $defs.theme holds the same keys, postures and every token, all required",
              tuple(entry["properties"]) == THEME_KEYS and entry["properties"]["posture"]["enum"] == list(MT.POSTURES)
              and entry["required"] == list(THEME_KEYS) and entry["properties"]["palette"]["required"] == list(TOKEN_NAMES)
              and tuple(entry["properties"]["palette"]["properties"]) == TOKEN_NAMES)
    ctx.check("field_help has a 3.3.12.0 line", "3.3.12.0" in field_help.PACK["contributes.themes"])
    plain = read_pack(fixture("doc-review"), "source")
    ctx.check(f"a pack without themes: no line, no palettes, got {plain.problems}", plain.problems == []
              and MT.themes_of(plain.manifest) == [] and MT.theme_lines(plain.manifest) == []
              and MT.palettes("doc-review", plain.manifest) == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
