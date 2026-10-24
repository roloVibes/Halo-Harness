"""tests.test_packs_fleet_contract -- a pack's `contributes.fleet` (Halo
3.2.0.0 R4, schemas/pack_yaml.py fleet(), packs/fleet_rules.py,
packs/contrib_views.py): the fixtures validate clean; the JSON schema twin has
the same keys; each failure fixture (a token and an environment reference in
an advertisement, a capability the top-level list does not name) is one line
per problem naming the key and its pack.yaml line; the other meanings are one
line each; a typo names the closest key; `halo pack inspect` lists Studio and
fleet contributions in one "contributes:" block with available / why, and
`halo pack doctor` has a row per capability not available here.

Run: python -m tests.test_packs_fleet_contract
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import DOC_REVIEW, FIXTURES, PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
TOOLS_ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True}


def _good() -> dict:
    import yaml
    return yaml.safe_load((DOC_REVIEW / "pack.yaml").read_text(encoding="utf-8"))


def _lines(data, root=None) -> list:
    from halo_harness.packs.manifest import validate_manifest
    return [ln for ln in validate_manifest(data, root=root) if "fleet" in ln]


@test
def test_the_fixtures_validate_and_the_twin_has_the_keys(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    from halo_harness.schemas.pack_yaml import CAPABILITY_KEYS, FLEET_KEYS, HARDWARE_KEYS, REQUIRES_KEYS
    for name in ("doc-review", "fleet-needs-gpu"):
        pack = read_pack(FIXTURES / name, "source")
        ctx.check(f"{name} validates clean, got {pack.problems}", pack.problems == [])
    fleet = _good()["contributes"]["fleet"]
    ctx.check(f"doc-review declares every fleet key, got {list(fleet)}", tuple(fleet) == FLEET_KEYS)
    cap = fleet["capabilities"][0]
    ctx.check("docs.review needs the bash grant and a model tag", cap["requires"] == {"models": ["tools"], "grants": ["bash"]}
              and cap["name"] in _good()["capabilities"])
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "pack.schema.json").read_text(encoding="utf-8"))
    d = schema["$defs"]
    ctx.check("the JSON twin's fleet keys", tuple(d["fleet"]["properties"]) == FLEET_KEYS)
    ctx.check("its capability keys", tuple(d["capability"]["properties"]) == CAPABILITY_KEYS)
    ctx.check("its requires keys", tuple(d["capability"]["properties"]["requires"]["properties"]) == REQUIRES_KEYS)
    ctx.check("its hardware keys", tuple(d["capability"]["properties"]["requires"]["properties"]["hardware"]["properties"]) == HARDWARE_KEYS)
    ctx.check("contributes.fleet points at it", schema["properties"]["contributes"]["properties"]["fleet"] == {"$ref": "#/$defs/fleet"})


@test
def test_each_failure_fixture_is_a_line_per_problem_with_its_line_number(ctx: Ctx):
    from halo_harness.packs.discover import read_pack
    probs = read_pack(FIXTURES / "fleet-secret", "source").problems
    ctx.check(f"fleet-secret: the token and the env reference, two lines, got {probs}", len(probs) == 2)
    ctx.check("the token: its key and line 12", bool(probs) and probs[0].startswith(
        "pack.yaml line 12: contributes.fleet.capabilities[0].description: a token-shaped value"))
    ctx.check("the env reference: its key and line 14", len(probs) > 1 and probs[1].startswith(
        "pack.yaml line 14: contributes.fleet.capabilities[0].requires.tools[0]: an environment reference ($HOME)"))
    ctx.check("neither line repeats the value", not any("ghp_" in p for p in probs))
    probs = read_pack(FIXTURES / "fleet-unknown-name", "source").problems
    ctx.check(f"fleet-unknown-name: one line, got {probs}", probs == [
        "pack.yaml line 11: contributes.fleet.capabilities[0].name 'docs.lint' is not in the pack's capabilities: list (docs.review)"])
    with PacksHome() as h:
        code, _out, err = h.cli("install", str(h.source("fleet-secret")))
        ctx.check(f"it does not install, got {code} {err!r}", code == 1 and "token-shaped" in err)


def _one(mutate, word: str, ctx: Ctx, root=None) -> None:
    data = _good()
    mutate(data["contributes"]["fleet"], data)
    lines = _lines(data, root)
    ctx.check(f"{word!r}: got {lines}", any(word in ln for ln in lines))


@test
def test_every_meaning_is_a_line(ctx: Ctx):
    cap = lambda fl: fl["capabilities"][0]  # noqa: E731
    req = lambda fl: cap(fl)["requires"]  # noqa: E731
    cases = [
        (lambda fl, d: req(fl).update(gpus=True), "requires.gpus is not a requires key"),
        (lambda fl, d: req(fl).update(hardwre={}), "closest: hardware"),
        (lambda fl, d: req(fl).update(grants=["network"]), "'network' is not a permission the pack requests"),
        (lambda fl, d: req(fl).update(locality=["desktop"]), "'desktop' is not one of repo, shared, pack-data, repo:<name>"),
        (lambda fl, d: req(fl).update(platform=["Linux 6"]), "is not a word"),
        (lambda fl, d: req(fl).update(hardware={"ram_gb": -2}), "ram_gb -2 is not a number of GB"),
        (lambda fl, d: cap(fl).update(capacity={"parallel": 0}), "capacity.parallel 0 is not 1..64"),
        (lambda fl, d: cap(fl).update(description="Reads C:\\Users\\someone\\docs first"), "description: holds a path"),
        (lambda fl, d: cap(fl).update(description="Reads /home/someone/docs first"), "description: holds a path"),
        (lambda fl, d: cap(fl).update(description="Reads ~/docs first"), "description: holds a path"),
        (lambda fl, d: req(fl).update(tools=["%APPDATA%"]), "an environment reference (%APPDATA%)"),
        (lambda fl, d: req(fl).update(tools=["${TOKEN}"]), "an environment reference (${TOKEN})"),
        (lambda fl, d: fl["mission"]["metadata"].update(key="Bearer abcdefghijklmnopqrstuvwx"), "a token-shaped value"),
        (lambda fl, d: fl["mission"]["metadata"].update(owner={"a": 1}), "a string, a number, true/false or a list of them"),
        (lambda fl, d: fl["capabilities"].append({"name": "docs.review"}), "'docs.review' is declared twice"),
        (lambda fl, d: fl["inspector"].append({"label": "x", "source": "../out.md"}), "is outside the pack's folder"),
        (lambda fl, d: fl["inspector"].append({"label": "x", "source": "fleet/run.py"}), "an inspector line reads a .md"),
        (lambda fl, d: fl["inspector"].append({"source": "fleet/checklist.md"}), "label: required"),
    ]
    for mutate, word in cases:
        _one(mutate, word, ctx)
    _one(lambda fl, d: fl["inspector"].append({"label": "x", "source": "fleet/missing.md"}), "fleet/missing.md is not in the pack", ctx, DOC_REVIEW)
    ctx.check("the fixture with its root is clean", _lines(_good(), DOC_REVIEW) == [])
    data = _good()
    data["contributes"]["fleet"]["capabilites"] = []
    ctx.check("a typo in fleet names 'capabilities'", any("capabilites" in ln and "'capabilities'" in ln for ln in _lines(data)))
    data = _good()
    data["contributes"]["fleet"]["capabilities"][0]["capacty"] = {}
    ctx.check("a typo in a capability names 'capacity'", any("capacty" in ln and "'capacity'" in ln for ln in _lines(data)))


@test
def test_inspect_lists_studio_and_fleet_contributions_with_available_and_why(ctx: Ctx):
    with PacksHome() as h:
        h.catalog([TOOLS_ROW])
        h.install(h.source(), enable=True, grants=["bash"])
        h.install(h.source("fleet-needs-gpu"), enable=True)
        code, out, _err = h.cli("inspect", "doc-review")
        block = out.split("contributes:\n", 1)[-1].split("permissions it requests:", 1)[0]
        ctx.check(f"one contributes block, got {out!r}", code == 0 and out.count("contributes:") == 1)
        ctx.check(f"its Studio part, got {block!r}", "Studio section docs (Docs review): notes (markdown), checks (table), links (links)"
                  in block and "Studio panel in session: reviews (events)" in block and "palette: Open the review checks" in block)
        ctx.check("its fleet capability, available, why", "fleet capability docs.review: available here "
                  "(tools: or:anthropic/claude-sonnet-4.6; bash granted); 2 at once" in block)
        ctx.check("the inspector line and the mission metadata", "mission inspector line: Review checklist (fleet/checklist.md)" in block
                  and "mission metadata: review=docs, style=short" in block)
        code, out, _err = h.cli("inspect", "doc-review", "--json")
        fl = json.loads(out)["contributes"]["fleet"]
        ctx.check(f"--json: contributes.fleet, got {fl['capabilities'][0]['available']}", fl["capabilities"][0]["available"] is True
                  and fl["inspector"][0]["source"] == "fleet/checklist.md" and json.loads(out)["contributes"]["studio"]["config_form"] is True)
        code, out, _err = h.cli("inspect", "fleet-needs-gpu")
        ctx.check(f"not available, why = no GPU here, got {out!r}", "fleet capability gpu.render: not available here (no GPU here)" in out)
        code, out, _err = h.cli("doctor")
        ctx.check(f"doctor: a row for it, got {out!r}", "[WARN] fleet-needs-gpu: fleet capability gpu.render is not available here: "
                  "no GPU here -> the fleet sends parts needing it to a harness that has it" in out)
        ctx.check("and none for the available one", "fleet capability docs.review" not in out)
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        h.cli("disable", "doc-review")
        enable(find("doc-review", cwd=h.repo))
        code, out, _err = h.cli("doctor")
        ctx.check(f"bash not granted: the row names the grant, got {out!r}", "doc-review: fleet capability docs.review is not available here: "
                  "bash not granted (halo pack enable doc-review --grant bash) -> halo pack enable doc-review --grant bash" in out)
        code, out, _err = h.cli("inspect", str(FIXTURES / "rare-caps"))
        ctx.check("a pack with no Studio or fleet part has no contributes block", code == 0 and "contributes:" not in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
