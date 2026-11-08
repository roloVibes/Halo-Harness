"""tests.test_pack_new -- `halo pack new` (Halo 3.3.12.0 R4, docs/PACK-AUTHORING.md): every single kind and --all
scaffold into a scratch home, `halo pack inspect` reads each clean, an install (project) and an enable with every
grant are clean, `halo pack doctor` has nothing to say about it (a model with the bios' tags in the catalog, a fake
`rg` on PATH), the README names every file, HALO-PACK.md and the entry command are there; the expansion set (two
full bios, a two-role lineup, a two-stage workflow that ends in the artifact, two skills); the `requires:` block
(each bad value one line; the doctor's missing-requirement row without rg and none with a fake one); the bundle;
--github and --no-github; a folder already there and a bad id refused with one line. No model, no network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pack_kit import KitHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _clean(ctx, k, folder: Path, what: str) -> None:
    pid = folder.name
    code, out, _err = k.cli("inspect", str(folder))
    ctx.check(f"{what}: inspect reads it clean, got {out[-300:]}", code == 0 and "problems: none" in out)
    code, out, err = k.cli("install", str(folder), "--project")
    ctx.check(f"{what}: installs into the project, got {err}", code == 0)
    code, out, err = k.cli("enable", pid, "--grant-all")
    ctx.check(f"{what}: enables with every grant, got {err}", code == 0)
    with k.path(fake_rg=True):
        code, out, _err = k.cli("doctor", "--json")
    rows = [p for p in json.loads(out)["problems"] if p["severity"] != "info"]
    ctx.check(f"{what}: halo pack doctor has nothing to say, got {rows}", code == 0 and not rows)
    readme = (folder / "README.md").read_text(encoding="utf-8")
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    missing = [f for f in files if f"`{f}`" not in readme]
    ctx.check(f"{what}: the README names every file, missing {missing}", not missing)
    ctx.check(f"{what}: HALO-PACK.md and the entry command are there", (folder / "HALO-PACK.md").is_file()
              and (folder / "commands" / f"{pid}.md").is_file())
    k.cli("remove", pid)


@test
def test_every_kind_alone_is_clean(ctx: Ctx):
    from halo_harness.packs.scaffold.kinds import KINDS, themes_known
    with KitHome() as k:
        for kind in KINDS:
            if kind == "themes" and not themes_known():
                from halo_harness.packs.scaffold import new
                ok, lines = new("only-themes", kinds=["themes"], folder=k.work)
                ctx.check(f"themes before R2 merges: one line, got {lines}", not ok and len(lines) == 1
                          and "contributes.themes" in lines[0] and not (k.work / "only-themes").exists())
                continue
            _clean(ctx, k, k.new(f"only-{kind}", kind), kind)


@test
def test_all_kinds_and_the_base(ctx: Ctx):
    with KitHome() as k:
        _clean(ctx, k, k.new("everything", all_kinds=True), "--all")
        _clean(ctx, k, k.new("bare"), "no kinds (the base)")
        entry = (k.work / "everything" / "commands" / "everything.md").read_text(encoding="utf-8")
        ctx.check("the entry command lists the commands, the workflow and the lineup",
                  all(s in entry for s in ("/everything:hello", "/everything:search", "everything/flow",
                                            "everything--crew", "$ARGUMENTS")))
        guide = (k.work / "everything" / "HALO-PACK.md").read_text(encoding="utf-8")
        ctx.check("HALO-PACK.md has the contract, the loop and the rules",
                  all(s in guide for s in ("## The contract in one page", "## The loop", "## The rules",
                                            "halo pack test .", "halo pack install . --link --project",
                                            "No telemetry", "No secret in a file", "/everything")))


@test
def test_the_expansion_set(ctx: Ctx):
    import yaml
    with KitHome() as k:
        folder = k.new("expand", "workflows", "teams")
        lead = yaml.safe_load((folder / "agents" / "lead.yaml").read_text(encoding="utf-8"))
        ctx.check("workflows brings the bios, the artifact and the skills", all((folder / p).exists() for p in (
            "agents/lead.yaml", "agents/checker.yaml", "artifacts/report.json", "skills/brief/SKILL.md",
            "skills/checklist/SKILL.md")))
        ctx.check("a bio shows every section: models, tools, context (skills, memory, prompt), limits, output, "
                  "environment, acceptance", all(s in lead for s in ("models", "tools", "context", "limits", "output",
                                                                      "environment", "acceptance"))
                  and lead["context"]["memory"]["namespace"] == "notes" and lead["context"]["skills"] == ["expand:brief"]
                  and "local" in lead["models"]["capabilities"] and lead["description"].startswith("Pick me"))
        crew = yaml.safe_load((folder / "teams" / "crew.yaml").read_text(encoding="utf-8"))
        ctx.check("the lineup: two roles, two tiers, acceptance, the workflow",
                  len(crew["agents"]) == 2 and len(crew["tiers"]) == 2 and crew["acceptance"] and crew["workflows"] == ["flow"])
        flow = yaml.safe_load((folder / "workflows" / "flow.yaml").read_text(encoding="utf-8"))
        ctx.check("the workflow: two stages, both roles, ending in the artifact",
                  [s["role"] for s in flow["stages"]] == ["lead", "checker"]
                  and flow["outputs"]["report"]["type"] == "artifact:report" and "expand:brief" in flow["stages"][0]["brief"])
        alone = k.new("lineup-only", "teams")
        ctx.check("a lineup without the workflows kind names no workflow",
                  "workflows" not in yaml.safe_load((alone / "teams" / "crew.yaml").read_text(encoding="utf-8")))


@test
def test_the_requires_block(ctx: Ctx):
    from halo_harness.packs.manifest_requires import requires_lines
    good = {"kind": "command", "name": "rg", "version": ">=13", "install": {"windows": "w", "linux": "l", "mac": "m"},
            "url": "https://github.com/BurntSushi/ripgrep", "license": "MIT", "why": "search"}
    ctx.check("a good tool entry and a pack entry beside it read clean",
              requires_lines({"requires": [{"pack": "base"}, good]}) == [])
    bad_kind = requires_lines({"requires": [{**good, "kind": "brew"}]})
    ctx.check(f"a bad kind: one line, got {bad_kind}", bad_kind == ["requires[0].kind: 'brew' is not one of command, "
                                                                    "python, npm, git"])
    no_mac = requires_lines({"requires": [{**good, "install": {"windows": "w", "linux": "l"}}]})
    ctx.check(f"a missing install line: one line, got {no_mac}",
              no_mac == ["requires[0].install: no line for mac (the owner's install line on each OS)"])
    bad_version = requires_lines({"requires": [{**good, "version": "latest"}]})
    ctx.check(f"a version that is not a range: one line, got {bad_version}",
              bad_version == ["requires[0].version: 'latest' is not a range (>=1.2, <=2.0 or 1.2, a minimum)"])
    with KitHome() as k:
        folder = k.new("wrap", "integration")
        k.cli("install", str(folder), "--project")
        k.cli("enable", "wrap", "--grant-all")
        with k.path():
            code, out, _err = k.cli("doctor")
            needs = k.manager_needs("wrap")
        ctx.check(f"no rg on PATH: the missing-requirement row with the install line, got {out}", code == 1
                  and "[WARN] wrap: needs rg (command): rg is not on PATH" in out and "Halo never installs" in out)
        ctx.check(f"the Pack Manager's row says needs rg, got {needs}", needs == ["needs rg"])
        with k.path(fake_rg=True):
            code, out, _err = k.cli("doctor")
        ctx.check(f"a fake rg on PATH: no row, got {out}", code == 0 and "needs rg" not in out)
        readme = (folder / "README.md").read_text(encoding="utf-8")
        ctx.check("the README's Install section comes from requires:", "## Install" in readme
                  and "winget install BurntSushi.ripgrep.MSVC" in readme and "MIT OR Unlicense" in readme)


@test
def test_the_bundle_block(ctx: Ctx):
    import yaml
    from halo_harness.packs.manifest_bundle import block
    with KitHome() as k:
        folder = k.new("keep-warm", "bundle")
        _code, out, _err = k.cli("inspect", str(folder))
        b = block(yaml.safe_load((folder / "pack.yaml").read_text(encoding="utf-8")))
        ctx.check(f"a bundle block with needs, a reservation and routing, got {b}", "problems: none" in out
                  and b["needs"]["chat"]["any_of"] and b["reservation"]["model"] == "chat"
                  and b["routing"]["task_work"] == "coder-or-cloud")


@test
def test_github_files_and_no_github(ctx: Ctx):
    import yaml
    from halo_harness import __version__
    with KitHome() as k:
        folder = k.new("hosted")
        ci = yaml.safe_load((folder / ".github" / "workflows" / "pack-test.yml").read_text(encoding="utf-8"))
        steps = " ".join(str(s.get("run") or "") for s in ci["jobs"]["pack-test"]["steps"])
        ctx.check("--github: LICENSE (MIT), .gitignore and the workflow", (folder / ".gitignore").is_file()
                  and (folder / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))
        ctx.check(f"the workflow parses, runs on ubuntu and windows and pins Halo at v{__version__}, got {steps}",
                  ci["jobs"]["pack-test"]["strategy"]["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]
                  and f"Halo-Harness@v{__version__}" in steps and "halo pack test ." in steps)
        readme = (folder / "README.md").read_text(encoding="utf-8")
        ctx.check("the README says how to install from GitHub", "## Install from GitHub" in readme
                  and "halo pack sources add" in readme)
        bare = k.new("local-only", github=False, license_id="Apache-2.0")
        ctx.check("--no-github: none of the three", not any((bare / p).exists() for p in (
            "LICENSE", ".gitignore", ".github")) and "## Install from GitHub" not in (bare / "README.md").read_text(encoding="utf-8"))
        other = k.new("apache", license_id="Apache-2.0")
        ctx.check("--license Apache-2.0: pack.yaml and LICENSE say it", "license: Apache-2.0" in
                  (other / "pack.yaml").read_text(encoding="utf-8") and "Apache-2.0" in (other / "LICENSE").read_text(encoding="utf-8"))


@test
def test_refusals_are_one_line(ctx: Ctx):
    with KitHome() as k:
        k.new("taken")
        code, _out, err = k.cli("new", "taken", "--dir", str(k.work))
        ctx.check(f"a folder already there: one line, exit 1, got {err}", code == 1 and len(err.strip().splitlines()) == 1
                  and "is already there" in err)
        code, _out, err = k.cli("new", "Bad_Id", "--dir", str(k.work))
        ctx.check(f"a bad id: the names rule, got {err}", code == 1 and "is not a pack id: lower-case letters" in err
                  and not (k.work / "Bad_Id").exists())
        code, _out, err = k.cli("new", "fine", "--kinds", "agents,cards", "--dir", str(k.work))
        ctx.check(f"an unknown kind: usage, the kinds named, got {err}", code == 2 and "cards is not a kind" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
