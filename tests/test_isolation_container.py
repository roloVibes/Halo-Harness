"""tests.test_isolation_container -- Halo 3.1.8.0 R5: `isolation: container` (isolation/container.py, seed.py,
lane.py through orchestra/adapters.py `spawn_worker`), `halo isolation image|build`, and that nothing changes
when nothing is declared. No docker or podman ever runs: the worker's runner is a recorder and `which` sees
only the rig's temp bin folder. No model is called.

Run: python -m tests.test_isolation_container
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.isolation_rig import IsoEnv, Recorder, run_with_lane
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
_TOKEN_VALUE = "made-up-github-value-0042"


def _spawn(run_dir, lane, runner, team=None):
    from halo_harness.orchestra.adapters import spawn_worker
    return spawn_worker("or:cheap/model", run_dir=run_dir, runner=runner, team=team)(lane)


def _lane_file(run_dir) -> dict:
    return json.loads((Path(run_dir) / "lanes" / "2.json").read_text(encoding="utf-8"))


@test
def test_wrap_builds_the_docker_argv_and_env(ctx: Ctx):
    with IsoEnv() as e:
        docker = e.tool("docker")
        data_dir = e.root / "data"
        data_dir.mkdir()
        e.lineup("boxed", {"agents": [{"agent": "coder", "role": "main"}],
                           "isolation": {"mode": "container", "image": "halo-test:1", "network": "none",
                                         "mounts": [f"{data_dir}:/data:ro"], "env": ["GITHUB_TOKEN"]}})
        e.bio("coder", {})
        os.environ["GITHUB_TOKEN"] = _TOKEN_VALUE
        try:
            _repo, run_dir, lane = run_with_lane(lineup="boxed")
            rec = Recorder()
            result = _spawn(run_dir, lane, rec)
        finally:
            os.environ.pop("GITHUB_TOKEN", None)
        argv, env = rec.calls[0]["argv"], rec.calls[0]["env"]
        wt, run = str(lane.worktree.resolve()), str(Path(run_dir).resolve())
        state = str((Path(run_dir) / "state-2").resolve())
        ctx.check(f"docker run --rm, and network: none still means no network, got {argv[:5]}",
                  Path(argv[0]) == docker and argv[1:5] == ["run", "--rm", "--network", "none"])
        pairs = [argv[i:i + 2] for i in range(len(argv) - 1)]
        for pair in (["-v", f"{wt}:/work"], ["-w", "/work"], ["-v", f"{run}:/run"], ["-v", f"{state}:/root/.halo"],
                     ["-v", f"{data_dir}:/data:ro"], ["-e", "HALO_ORCHESTRA_RUN=/run"], ["-e", "HALO_ORCHESTRA_LANE=2"],
                     ["-e", "GITHUB_TOKEN"]):
            ctx.check(f"argv has {pair}", pair in pairs)
        i = argv.index("halo-test:1")
        ctx.check(f"the image, then `halo -p` with the worker's own flags, got {argv[i:i + 4]}",
                  argv[i + 1:i + 4] == ["halo", "-p", "write subtotal"] and argv[-2:] == ["--model", "or:cheap/model"])
        ctx.check("a value never sits in the argv", not any(_TOKEN_VALUE in a for a in argv))
        ctx.check("the value rides in the docker process's env", env.get("GITHUB_TOKEN") == _TOKEN_VALUE)
        host_halo = str(e.state.resolve())
        ctx.check("the host's ~/.halo is never mounted", not any(a.startswith(host_halo + ":") for a in argv))
        data = _lane_file(run_dir)
        ctx.check(f"the lane records the isolation, got {data.get('isolation')}",
                  data.get("isolation", {}).get("mode") == "container" and data["isolation"].get("image") == "halo-test:1")
        ctx.check("and its line", data.get("opt_ins") == ["isolation: container (halo-test:1)"])
        ctx.check(f"the worker's result comes back, got {result}", result.get("ok") is True and result.get("text") == "done")


@test
def test_isolation_container_alone_takes_the_defaults(ctx: Ctx):
    with IsoEnv() as e:
        e.tool("docker")
        e.lineup("plain-box", {"agents": [{"agent": "coder", "role": "main"}], "isolation": "container"})
        e.bio("coder", {})
        _repo, run_dir, lane = run_with_lane(lineup="plain-box")
        rec = Recorder()
        _spawn(run_dir, lane, rec)
        argv = rec.calls[0]["argv"]
        from halo_harness.isolation.container import default_image
        ctx.check(f"the host network by default (a worker reaches its model), got {argv[3:5]}",
                  argv[3:5] == ["--network", "host"])
        from halo_harness.isolation.spec import isolation_of
        ctx.check("a mapping that names no network takes host too",
                  isolation_of({"mode": "container", "image": "x"})["network"] == "host")
        ctx.check("the default image", default_image() in argv and default_image().startswith("halo-harness-worker:"))
        names = [argv[i + 1] for i, a in enumerate(argv) if a == "-e"]
        ctx.check(f"only the run's own variables cross in, got {names}",
                  all(n.startswith(("HALO_", "PYTHONIOENCODING")) for n in names))


@test
def test_podman_when_there_is_no_docker(ctx: Ctx):
    with IsoEnv() as e:
        podman = e.tool("podman")
        e.lineup("boxed", {"agents": [{"agent": "coder", "role": "main"}], "isolation": "container"})
        e.bio("coder", {})
        _repo, run_dir, lane = run_with_lane(lineup="boxed")
        rec = Recorder()
        _spawn(run_dir, lane, rec)
        ctx.check("podman runs it", Path(rec.calls[0]["argv"][0]) == podman)


@test
def test_no_docker_or_podman_stops_the_lane_with_one_line(ctx: Ctx):
    with IsoEnv() as e:
        e.lineup("boxed", {"agents": [{"agent": "coder", "role": "main"}], "isolation": "container"})
        e.bio("coder", {})
        _repo, run_dir, lane = run_with_lane(lineup="boxed")
        rec = Recorder()
        result = _spawn(run_dir, lane, rec)
        ctx.check(f"the one line, got {result}",
                  result == {"ok": False, "error": "isolation: container asked, no docker or podman on this host"})
        ctx.check("no worker started", not rec.calls)
        ctx.check("the lane still says what it asked for", _lane_file(run_dir).get("isolation", {}).get("mode") == "container")


@test
def test_the_scoped_state_dir_is_seeded_without_credentials(ctx: Ctx):
    with IsoEnv() as e:
        e.tool("docker")
        made_up = "made-up-dbx-value-77"
        (e.state / "config.json").write_text(json.dumps({
            "model": "or:cheap/model", "theme": "holo", "roles": {"coder": "or:cheap/model"},
            "databricks": {"host": "https://example.invalid", "token": made_up},
            "openai": {"api_key": made_up, "base_url": "https://example.invalid/v1"}}), encoding="utf-8")
        (e.state / "models.json").write_text("{}", encoding="utf-8")
        e.lineup("boxed", {"agents": [{"agent": "boss", "role": "main"}, {"agent": "coder", "role": "subagent"}],
                           "isolation": "container"})
        e.bio("boss", {})
        e.bio("coder", {"extends": "boss", "models": {"preference": "or:cheap/model"}})
        _repo, run_dir, lane = run_with_lane(lineup="boxed")
        _spawn(run_dir, lane, Recorder())
        state = Path(run_dir) / "state-2"
        cfg = json.loads((state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"the model config is there, got {sorted(cfg)}", cfg.get("model") == "or:cheap/model" and "roles" in cfg)
        ctx.check("a key-shaped field is dropped at any depth", "token" not in cfg.get("databricks", {})
                  and "api_key" not in cfg.get("openai", {}) and cfg["databricks"].get("host"))
        ctx.check("a key the worker does not need is not copied", "theme" not in cfg)
        ctx.check("the catalog and the lineup files it needs", (state / "models.json").is_file()
                  and (state / "teams" / "boxed.yaml").is_file() and (state / "agents" / "coder.yaml").is_file()
                  and (state / "agents" / "boss.yaml").is_file())
        ctx.check("a bio's extends is folded in", "extends" not in (state / "agents" / "coder.yaml").read_text(encoding="utf-8"))
        leaked = [p for p in state.rglob("*") if p.is_file() and made_up in p.read_text(encoding="utf-8", errors="replace")]
        ctx.check(f"no file in it holds the value, got {leaked}", not leaked)


@test
def test_nothing_declared_changes_nothing(ctx: Ctx):
    with IsoEnv() as e:
        e.tool("docker")
        e.lineup("open", {"agents": [{"agent": "coder", "role": "main"}]})
        e.bio("coder", {})
        _repo, run_dir, lane = run_with_lane(lineup="open")
        rec = Recorder()
        _spawn(run_dir, lane, rec)
        from halo_harness.orchestra.adapters import worker_argv
        ctx.check("the argv as before", rec.calls[0]["argv"] == worker_argv("write subtotal", "or:cheap/model"))
        env = rec.calls[0]["env"]
        ctx.check("no opt-in variable in the env", not any(k in env for k in
                  ("HALO_TOOLS_CAPS", "HALO_OPT_INS", "HALO_SECRET_KEYS", "BRIDGE_STATE_DIR") if k not in os.environ))
        data = _lane_file(run_dir)
        ctx.check("the lane file has no opt-in field", not any(k in data for k in ("isolation", "secrets", "tools", "opt_ins")))
        ctx.check("no scoped state dir", not (Path(run_dir) / "state-2").exists())


@test
def test_halo_isolation_image_and_build(ctx: Ctx):
    with IsoEnv() as e:
        from halo_harness import __version__
        from halo_harness.isolation.cli import cmd_isolation
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_isolation(["image"], which=e.which)
        text = out.getvalue()
        ctx.check("image prints the default name and the Dockerfile", rc == 0 and f"halo-harness-worker:{__version__}" in text
                  and "FROM python:" in text and "pip install" in text and "@v${HALO_VERSION}" in text)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = cmd_isolation(["build"], which=e.which)
        ctx.check(f"no engine: build says so, rc 1, got {rc}", rc == 1 and "no docker or podman" in err.getvalue())
        e.tool("docker")
        calls = []
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_isolation(["build", "--image", "halo-test:2"], which=e.which,
                               runner=lambda argv, **kw: calls.append(argv) or __import__("subprocess").CompletedProcess(argv, 0))
        ctx.check(f"build runs `docker build` once with the version, got {calls}", rc == 0 and len(calls) == 1
                  and calls[0][1:4] == ["build", "-t", "halo-test:2"] and f"HALO_VERSION={__version__}" in calls[0])
        calls.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cmd_isolation(["build", "--dry-run"], which=e.which, runner=lambda argv, **kw: calls.append(argv))
        ctx.check("--dry-run runs nothing", rc == 0 and not calls)


@test
def test_the_declaration_is_validated(ctx: Ctx):
    from halo_harness.isolation.spec import isolation_problems
    ctx.check("container and user are fine", not isolation_problems("container") and not isolation_problems("user"))
    ctx.check("an unknown mode is one line", isolation_problems({"mode": "vm"}) == ['"isolation.mode" \'vm\' is not one of container, user'])
    ctx.check("a bad network and a stray key", len(isolation_problems({"network": "bridge", "cpu": 2})) == 2)
    ctx.check("user mode needs a user", isolation_problems({"mode": "user"}) == ['"isolation.user" is required with mode user'])
    with IsoEnv() as e:
        e.bio("coder", {})
        from halo_harness.teams_yaml import validate_team_template
        ok = validate_team_template({"agents": [{"agent": "coder", "role": "main"}], "isolation": "container"})
        bad = validate_team_template({"agents": [{"agent": "coder", "role": "main"}], "isolation": "vm"})
        ctx.check(f"a lineup's isolation is checked, got {ok} / {bad}", not ok and any("isolation" in p for p in bad))


# ---- 3.6.0.1 (reaper batch 1): a container lane has a name, a record, and ends with its Halo --------------------------

def _boxed(e):
    """A recording fake docker on the rig's PATH and a lane whose lineup asks for a container."""
    e.tool("docker", record=True)
    e.lineup("boxed", {"agents": [{"agent": "coder", "role": "main"}], "isolation": "container"})
    e.bio("coder", {})
    return run_with_lane(lineup="boxed")


def _flag(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


def _records(e) -> list:
    d = e.state / "containers"
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def _dead_pid() -> int:
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait(timeout=60)
    return p.pid


@test
def test_container_lane_has_a_name_and_the_owner_label(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.isolation.container import name_of
    with IsoEnv() as e:
        _repo, run_dir, lane = _boxed(e)
        rec = Recorder()
        result = _spawn(run_dir, lane, rec)
        argv = rec.calls[0]["argv"]
        name, label = _flag(argv, "--name"), _flag(argv, "--label")
        mark = closing.my_ident()
        ctx.check(f"the container is named for this Halo and the lane, got {name}",
                  bool(name) and name.startswith(f"halo-{mark}-2-"))
        ctx.check(f"and labelled with its owner, got {label}", label == f"halo.owner={mark}")
        ctx.check("name_of reads it back", name_of(argv) == name)
        ctx.check("name_of of a plain worker argv is None", name_of([sys.executable, "-m", "halo_harness", "-p", "x"]) is None)
        ctx.check(f"a lane that ended by itself leaves no record, got {_records(e)}", _records(e) == [])
        ctx.check("and no engine call", e.engine_calls() == [])
        ctx.check("the result comes back", result.get("ok") is True)


@test
def test_a_close_while_a_container_lane_runs_removes_it(ctx: Ctx):
    import subprocess
    from halo_harness import closing
    closing.reset_for_tests()
    try:
        with IsoEnv() as e:
            _repo, run_dir, lane = _boxed(e)
            seen: dict = {}

            def runner(argv, **kw):
                seen["argv"], seen["records"] = list(argv), _records(e)
                closing.close(polite_s=0.2, hard_s=0.1, say=lambda s: None, state_dir=e.state)
                out = json.dumps({"type": "result", "is_error": False, "result": "done", "total_cost_usd": 0})
                return subprocess.CompletedProcess(argv, 0, out + "\n", "")

            _spawn(run_dir, lane, runner)
            name = _flag(seen["argv"], "--name")
            ctx.check(f"while it runs, its record is there, got {seen['records']}", seen["records"] == [name])
            ctx.check(f"the close removed the container through the engine, got {e.engine_calls()}",
                      ["rm", "-f", name] in e.engine_calls())
            ctx.check(f"and its record, got {_records(e)}", _records(e) == [])
    finally:
        closing.reset_for_tests()


@test
def test_a_container_lane_past_its_time_removes_its_container(ctx: Ctx):
    import subprocess
    from halo_harness.orchestra.adapters import spawn_worker
    with IsoEnv() as e:
        _repo, run_dir, lane = _boxed(e)
        seen: dict = {}

        def runner(argv, **kw):
            seen["argv"] = list(argv)
            raise subprocess.TimeoutExpired(argv, 5)

        result = spawn_worker("or:cheap/model", run_dir=run_dir, runner=runner, timeout_s=5)(lane)
        name = _flag(seen["argv"], "--name")
        ctx.check(f"the same one line, got {result}", result == {"ok": False, "error": "the worker ran past 5s"})
        ctx.check(f"the container is removed, got {e.engine_calls()}", e.engine_calls() == [["rm", "-f", name]])
        ctx.check(f"and its record, got {_records(e)}", _records(e) == [])


@test
def test_a_failed_rm_keeps_the_record_for_the_next_start(ctx: Ctx):
    import subprocess
    with IsoEnv() as e:
        _repo, run_dir, lane = _boxed(e)
        (e.bin / "engine_fail").write_text("", encoding="utf-8")
        seen: dict = {}

        def runner(argv, **kw):
            seen["argv"] = list(argv)
            raise subprocess.TimeoutExpired(argv, 5)

        _spawn(run_dir, lane, runner)
        name = _flag(seen["argv"], "--name")
        ctx.check(f"the rm was tried, got {e.engine_calls()}", e.engine_calls() == [["rm", "-f", name]])
        ctx.check(f"it failed, so the record stays, got {_records(e)}", _records(e) == [name])


@test
def test_the_start_sweep_removes_a_container_whose_owner_is_gone(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.isolation import container
    with IsoEnv() as e:
        engine = str(e.tool("docker", record=True))
        lines = closing.sweep(state_dir=e.state, say=lambda s: None)
        ctx.check(f"no record: no engine call at start, got {e.engine_calls()} / {lines}",
                  e.engine_calls() == [] and lines == [])
        gone = closing.ident(_dead_pid(), "x")
        container.write_record("halo-gone-1-aaaaaa", engine, gone, state_dir=e.state)
        container.write_record("halo-live-1-bbbbbb", engine, closing.my_ident(), state_dir=e.state)
        said: list = []
        lines = closing.sweep(state_dir=e.state, say=said.append)
        ctx.check(f"the gone owner's container is removed, got {e.engine_calls()}",
                  e.engine_calls() == [["rm", "-f", "halo-gone-1-aaaaaa"]])
        ctx.check(f"its record goes, the live owner's stays, got {_records(e)}", _records(e) == ["halo-live-1-bbbbbb"])
        ctx.check(f"one line, got {said}", len(said) == 1 and "halo-gone-1-aaaaaa" in said[0]
                  and said[0].startswith("halo: removed a worker container left from ") and lines == said)


@test
def test_the_reaper_removes_its_owners_container(ctx: Ctx):
    from halo_harness import closing, subprocess_safe
    from halo_harness.isolation import container
    tree = Path(__file__).resolve().parent.parent
    with IsoEnv() as e:
        engine = str(e.tool("docker", record=True))
        dead = _dead_pid()
        mark = closing.ident(dead, "x")
        container.write_record("halo-mine-2-cccccc", engine, mark, state_dir=e.state)
        container.write_record("halo-other-2-dddddd", engine, closing.my_ident(), state_dir=e.state)
        proc = subprocess_safe.run([sys.executable, "-I", "-S", str(tree / "halo_harness" / "closing_reaper.py"),
                                    str(dead), "", mark, str(e.state), str(tree)],
                                   capture_output=True, text=True, timeout=60)
        ctx.check(f"the reaper exits 0, got {proc.returncode} {proc.stderr[-300:]!r}", proc.returncode == 0)
        ctx.check(f"it removed its owner's container only, got {e.engine_calls()}",
                  e.engine_calls() == [["rm", "-f", "halo-mine-2-cccccc"]])
        ctx.check(f"and that record only, got {_records(e)}", _records(e) == ["halo-other-2-dddddd"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
