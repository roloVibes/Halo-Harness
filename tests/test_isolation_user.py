"""tests.test_isolation_user -- Halo 3.1.8.0 R5: `isolation: user` (isolation/scoped_user.py, lane.py): the
POSIX argv (`sudo -n -u <name> --preserve-env=<names> -- ...`), the scoped state dir, the share step, the
Windows line, the doctor row's user part. sudo never runs: `which` finds a stand-in in the rig's bin folder,
the share step is recorded, and the doctor's probe runner is a fake. No model is called.

Run: python -m tests.test_isolation_user
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.isolation_rig import IsoEnv, run_with_lane
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()


def _worker_argv():
    from halo_harness.orchestra.adapters import worker_argv
    return worker_argv("write subtotal", "or:cheap/model")


def _env(run_dir, n=2):
    from halo_harness.orchestra.workers import child_env
    return dict(child_env(run_dir, n, os.environ), PYTHONIOENCODING="utf-8")


@test
def test_posix_argv_runs_the_worker_as_the_scoped_user(ctx: Ctx):
    with IsoEnv() as e:
        sudo = e.tool("sudo")
        e.lineup("scoped", {"agents": [{"agent": "coder", "role": "main"}],
                            "isolation": {"mode": "user", "user": "halo-worker", "env": ["GITHUB_TOKEN"]}})
        e.bio("coder", {})
        _repo, run_dir, lane = run_with_lane(lineup="scoped")
        shared = []
        env = dict(_env(run_dir), GITHUB_TOKEN="made-up-value-for-sudo-test")
        from halo_harness.isolation.lane import prepare
        argv, out_env, values = prepare(lane, _worker_argv(), env, run_dir=run_dir, platform="linux",
                                        sharer=lambda paths, spec: shared.append((paths, spec["user"])))
        ctx.check(f"sudo -n -u <name>, got {argv[:4]}", Path(argv[0]) == sudo and argv[1:4] == ["-n", "-u", "halo-worker"])
        ctx.check("then the preserved names and --", argv[4].startswith("--preserve-env=") and argv[5] == "--")
        ctx.check("then the worker's own argv, unchanged", argv[6:] == _worker_argv())
        names = argv[4].split("=", 1)[1].split(",")
        for name in ("HALO_ORCHESTRA_RUN", "HALO_ORCHESTRA_LANE", "BRIDGE_STATE_DIR", "PYTHONIOENCODING", "GITHUB_TOKEN"):
            ctx.check(f"{name} is preserved", name in names)
        ctx.check("names only: no value in the argv", not any("made-up-value" in a for a in argv) and "=" not in "".join(names))
        state = (Path(run_dir) / "state-2").resolve()
        ctx.check("the worker's state dir is the run's scoped one", out_env["BRIDGE_STATE_DIR"] == str(state) and state.is_dir())
        ctx.check(f"the worktree and the run folder are shared with the user first, got {shared}",
                  shared == [([lane.worktree, Path(run_dir)], "halo-worker")])
        ctx.check("no secret values for a lane without a broker", values == ())
        data = lane.data()
        ctx.check(f"the lane records the user, got {data.get('isolation')}",
                  data.get("isolation", {}).get("user") == "halo-worker" and data.get("opt_ins") == ["isolation: user (halo-worker)"])


@test
def test_windows_has_no_scoped_user(ctx: Ctx):
    with IsoEnv() as e:
        e.tool("sudo")
        e.fake_op({"op://vault/item/field": "made-up-op-value"})
        e.lineup("scoped", {"agents": [{"agent": "coder", "role": "main"}],
                            "isolation": {"mode": "user", "user": "halo-worker"}})
        e.bio("coder", {"secrets": {"broker": "1password"},
                        "environment": {"secrets": [{"env": "SERVICE_TOKEN", "ref": "op://vault/item/field"}]}})
        _repo, run_dir, lane = run_with_lane(lineup="scoped", bio="coder")
        from halo_harness.isolation import Stop
        from halo_harness.isolation.lane import prepare
        try:
            prepare(lane, _worker_argv(), _env(run_dir), run_dir=run_dir, platform="win32")
            line = None
        except Stop as err:
            line = str(err)
        ctx.check(f"the one line, got {line!r}", line == "isolation: user is not available on Windows; use container")
        ctx.check("checked before any secret is read", e.op_calls() == [])


@test
def test_no_sudo_is_one_line_too(ctx: Ctx):
    with IsoEnv() as e:
        e.lineup("scoped", {"agents": [{"agent": "coder", "role": "main"}], "isolation": {"mode": "user", "user": "w"}})
        e.bio("coder", {})
        _repo, run_dir, lane = run_with_lane(lineup="scoped")
        from halo_harness.isolation import Stop
        from halo_harness.isolation.lane import prepare
        try:
            prepare(lane, _worker_argv(), _env(run_dir), run_dir=run_dir, platform="linux", sharer=lambda *a: None)
            line = None
        except Stop as err:
            line = str(err)
        ctx.check(f"the line names sudo, got {line!r}", line == "isolation: user asked, no sudo on this host")


@test
def test_share_makes_the_folders_group_writable(ctx: Ctx):
    if os.name == "nt":
        raise SkipTest("chgrp/chmod group bits are POSIX")
    from halo_harness.isolation.scoped_user import share
    root = Path(tempfile.mkdtemp(prefix="iso-share-"))
    (root / "wt" / "other").mkdir(parents=True)
    (root / "wt" / "other" / "x.py").write_text("x", encoding="utf-8")
    (root / "claims.jsonl").write_text("", encoding="utf-8")
    os.chmod(root / "claims.jsonl", 0o600)
    share([root], os.getgid(), skip=[root / "wt"])
    import stat
    mode = (root / "claims.jsonl").stat().st_mode
    ctx.check("a run file is group read-write", mode & stat.S_IRGRP and mode & stat.S_IWGRP)
    ctx.check("a folder is setgid and group-reachable", (root / "wt").stat().st_mode & stat.S_ISGID
              and (root / "wt").stat().st_mode & stat.S_IXGRP)
    ctx.check("another lane's worktree is left as it was", not (root / "wt" / "other").stat().st_mode & stat.S_ISGID)


@test
def test_the_doctor_row_says_which_modes_this_host_runs(ctx: Ctx):
    with IsoEnv() as e:
        from halo_harness.isolation.doctor_rows import isolation_row
        declared = [("lineup scoped", {"mode": "user", "user": "halo-worker"}, None)]
        row = isolation_row(declared, which=e.which, platform="win32")
        ctx.check(f"Windows: the declared user mode is a WARN line, got {row}",
                  row.startswith("[WARN] Isolation: lineup scoped declares user: not available on Windows"))
        e.tool("sudo")
        probes = []

        def runner(argv, **kw):
            probes.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")
        row = isolation_row(declared, which=e.which, platform="linux", runner=runner)
        ctx.check(f"POSIX with sudo: the user can run, got {row}", row.startswith("[OK]") and "user (sudo)" in row
                  and "sudo -n as halo-worker: ok" in row)
        ctx.check(f"the probe is `sudo -n -u <name> true`, got {probes}", probes and probes[0][1:] == ["-n", "-u", "halo-worker", "true"])
        row = isolation_row(declared, which=e.which, platform="linux",
                            runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", ""))
        ctx.check("a password prompt is said as it is", "sudo -n as halo-worker: asks for a password" in row)
        probes.clear()
        isolation_row(declared, which=e.which, platform="linux", runner=runner, spawn=False)
        ctx.check("under the test switch no probe starts", probes == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
