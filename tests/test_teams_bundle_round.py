"""tests.test_teams_bundle_round -- Halo 2.0.6 round 13: export/import of
a lineup with its bios as one folder.

The roadmap's own "export/import bundles" item (deferred from 2.0.5
round 2): `halo teams export <name> --bundle <dir>` writes the FULL team
template plus every non-shipped bio it references into one folder;
`halo teams import <dir>` applies it on another box -- bios to USER
scope (never silently overwriting an existing non-shipped bio without
--force), the team through the validated save path. The exact manual scp
the owner did for halo-dev-cycle tonight, made one command.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


def _scoped(home: Path):
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)

    class _Scope:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return _Scope()


def _write_team(home: Path, name: str, agents: list) -> None:
    teams = home / ".halo" / "teams"
    teams.mkdir(parents=True, exist_ok=True)
    import yaml
    (teams / f"{name}.yaml").write_text(yaml.safe_dump({
        "name": name, "description": f"test team {name}", "version": 1,
        "agents": agents}, sort_keys=False), encoding="utf-8")


def _write_bio(home: Path, name: str, **extra) -> None:
    bios = home / ".halo" / "agents"
    bios.mkdir(parents=True, exist_ok=True)
    import yaml
    body = {"name": name, "description": f"bio {name}"}
    body.update(extra)
    (bios / f"{name}.yaml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


@test
def test_bundle_export_copies_team_and_bios_not_shipped_ones(ctx: Ctx):
    from halo_harness.teams_bundle import bundle_export
    home = Path(tempfile.mkdtemp(prefix="tb-exp-"))
    out = home / "bundle"
    with _scoped(home):
        _write_team(home, "my-team", [
            {"agent": "orchestrator", "role": "main", "as": "boss"},
            {"agent": "my-coder", "role": "subagent", "as": "worker"},
        ])
        _write_bio(home, "my-coder", models={"preference": "ol:qwen3-coder:30b@lan"})
        ok, lines = bundle_export("my-team", out)
        ctx.check(f"the export succeeds, got {lines}", ok is True)
        ctx.check("the folder carries the manifest and the team",
                  (out / "bundle.json").is_file() and (out / "team.yaml").is_file())
        manifest = json.loads((out / "bundle.json").read_text(encoding="utf-8"))
        ctx.check(f"the manifest names the copied bios, got {manifest}",
                  manifest.get("bios") == ["my-coder"] and manifest.get("name") == "my-team")
        ctx.check(f"the shipped bio is skipped, got {manifest.get('shipped_bios_skipped')}",
                  manifest.get("shipped_bios_skipped") == ["orchestrator"])
        ctx.check("the bio file itself landed",
                  (out / "bios" / "my-coder.yaml").is_file())
    # an unknown team refuses cleanly
    with _scoped(home):
        ok2, lines2 = bundle_export("no-such-team", home / "b2")
        ctx.check("an unknown team refuses", ok2 is False and any("no such team" in l for l in lines2))


@test
def test_bundle_import_round_trips_to_user_scope(ctx: Ctx):
    from halo_harness.teams_bundle import bundle_export, bundle_import
    src_home = Path(tempfile.mkdtemp(prefix="tb-src-"))
    out = src_home / "bundle"
    with _scoped(src_home):
        _write_team(src_home, "portable", [
            {"agent": "boss-bio", "role": "main", "as": "boss"},
            {"agent": "my-coder", "role": "subagent", "as": "worker"},
        ])
        _write_bio(src_home, "boss-bio")
        _write_bio(src_home, "my-coder", models={"preference": "or:vendor/x"})
        ok, _lines = bundle_export("portable", out)
        assert ok

    # a DIFFERENT machine: fresh home, same bundle folder
    dst_home = Path(tempfile.mkdtemp(prefix="tb-dst-"))
    with _scoped(dst_home):
        ok, lines = bundle_import(out)
        ctx.check(f"the import succeeds, got {lines}", ok is True)
        ctx.check("the team landed in user scope",
                  (dst_home / ".halo" / "teams" / "portable.yaml").is_file())
        ctx.check("both bios landed in USER scope",
                  (dst_home / ".halo" / "agents" / "boss-bio.yaml").is_file()
                  and (dst_home / ".halo" / "agents" / "my-coder.yaml").is_file())
        from halo_harness.teams_yaml import resolve_team_template
        from halo_harness.agents_yaml import resolve_agent_bio
        ctx.check("the imported team resolves with its bios",
                  resolve_team_template("portable") is not None
                  and resolve_agent_bio("my-coder") is not None)


@test
def test_import_never_silently_overwrites_a_colliding_bio(ctx: Ctx):
    from halo_harness.teams_bundle import bundle_export, bundle_import
    src_home = Path(tempfile.mkdtemp(prefix="tb-coll-src-"))
    out = src_home / "bundle"
    with _scoped(src_home):
        _write_team(src_home, "collide", [{"agent": "shared-bio", "role": "main", "as": "boss"}])
        _write_bio(src_home, "shared-bio", description="the bundle's version")
        ok, _ = bundle_export("collide", out)
        assert ok
    dst_home = Path(tempfile.mkdtemp(prefix="tb-coll-dst-"))
    with _scoped(dst_home):
        _write_bio(dst_home, "shared-bio", description="the LOCAL version")
        ok, lines = bundle_import(out)
        ctx.check("the import still succeeds (the team lands)", ok is True)
        ctx.check("the collision is reported",
                  any("SKIPPED" in l and "shared-bio" in l for l in lines))
        local = (dst_home / ".halo" / "agents" / "shared-bio.yaml").read_text(encoding="utf-8")
        ctx.check("the LOCAL bio is untouched without --force",
                  "the LOCAL version" in local)
        ok2, lines2 = bundle_import(out, force=True)
        local2 = (dst_home / ".halo" / "agents" / "shared-bio.yaml").read_text(encoding="utf-8")
        ctx.check("--force overwrites with the bundle's version",
                  ok2 is True and "the bundle's version" in local2)


@test
def test_the_cli_wires_bundle_both_ways(ctx: Ctx):
    import subprocess
    src_home = Path(tempfile.mkdtemp(prefix="tb-cli-src-"))
    out = src_home / "bundle"
    with _scoped(src_home):
        _write_team(src_home, "cli-team", [{"agent": "cli-bio", "role": "main", "as": "boss"}])
        _write_bio(src_home, "cli-bio")
        env = {k: v for k, v in os.environ.items()
               if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        env.update({"BRIDGE_TEST_HOME": str(src_home), "PYTHONPATH": str(REPO_DIR)})
        r = subprocess.run([sys.executable, "-m", "halo_harness", "teams", "export",
                            "cli-team", "--bundle", str(out)],
                           env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=120)
        ctx.check(f"export --bundle exits 0, got {r.returncode} err={r.stderr[-200:]!r}",
                  r.returncode == 0 and (out / "bundle.json").is_file())
    dst_home = Path(tempfile.mkdtemp(prefix="tb-cli-dst-"))
    with _scoped(dst_home):
        env = {k: v for k, v in os.environ.items()
               if k not in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        env.update({"BRIDGE_TEST_HOME": str(dst_home), "PYTHONPATH": str(REPO_DIR)})
        r2 = subprocess.run([sys.executable, "-m", "halo_harness", "teams", "import", str(out)],
                            env=env, cwd=str(REPO_DIR), capture_output=True, text=True, timeout=120)
        ctx.check(f"import <dir> exits 0, got {r2.returncode} out={r2.stdout[-200:]!r}",
                  r2.returncode == 0)
        ctx.check("the hint names the activation command", "halo teams use cli-team" in r2.stdout)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
