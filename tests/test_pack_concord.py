"""tests.test_pack_concord -- the concord pack Halo ships (Halo 3.3.10.0 R3, halo_harness/templates/packs/concord/;
docs/PACKS.md "The concord pack"). A FAKE `concord` (tests/helpers/fake_concord.py) first on PATH in a scratch bin
dir; never the real `concord` or `concord-mcp`, nothing downloaded or installed, no network:

1. the manifest validates with no problem; the description says telemetry is on upstream and the pack turns it off;
   permissions are hooks and mcp:concord; `.mcp.json` runs `concord-mcp` with CONCORD_TELEMETRY_DISABLED=1 and
   CONCORD_REPO_ROOT from ${CLAUDE_PROJECT_DIR}, which Halo fills with the project folder; the hooks are Concord's
   four commands, each with telemetry off;
2. installed by id from the shipped folder, enabled with the two grants, `halo pack mode concord coordinating on`
   arms claimed-files;
3. the policy: deny with the pack's line on the claimed path (`concord check claimed.txt` run in the project folder,
   telemetry off), allow on another, `--task` passed from CONCORD_TASK (and that task's own claim then allowed),
   allow when no `concord` is on PATH; a path outside the project is not checked;
4. `halo pack doctor` with the pack enabled and no `concord-mcp` on PATH: one warns row, not-on-path.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import fake_concord  # noqa: E402
from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LINE = "policy: deny -- claimed-files: concord: claimed.txt is claimed by task t-42 (pack concord, rule claimed)"


def _root() -> Path:
    from halo_harness.packs.sources import shipped_dir
    return shipped_dir() / "concord"


@contextmanager
def _path(*dirs, **env):
    """PATH = the given dirs + Python's own folder (nothing else: no real concord can be found); env set and restored."""
    keys = ["PATH", *env]
    saved = {k: os.environ.get(k) for k in keys}
    os.environ["PATH"] = os.pathsep.join([str(d) for d in dirs] + [str(Path(sys.executable).parent)])
    os.environ.update({k: str(v) for k, v in env.items()})
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_the_manifest_the_server_and_the_hooks(ctx: Ctx):
    from halo_harness.config.plugins import discover_plugin_mcp_servers
    from halo_harness.packs.discover import read_pack
    pack = read_pack(_root(), "source", folder_is_id=True)
    ctx.check(f"it validates, got {pack.problems}", pack.problems == [] and pack.id == "concord")
    ctx.check(f"the telemetry sentence, got {pack.description!r}", "Concord's telemetry to getconcord.ai is on by default "
              "upstream, and this pack turns it off (CONCORD_TELEMETRY_DISABLED=1)." in pack.description)
    ctx.check("hooks and mcp:concord", pack.manifest["permissions"] == ["hooks", "mcp:concord"])
    mcp = json.loads((_root() / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["concord"]
    ctx.check(f"the owner's concord-mcp, telemetry off, got {mcp}", mcp["command"] == "concord-mcp"
              and mcp["env"] == {"CONCORD_TELEMETRY_DISABLED": "1", "CONCORD_REPO_ROOT": "${CLAUDE_PROJECT_DIR}"})
    with PacksHome() as h:
        servers, notices = discover_plugin_mcp_servers(env={}, extra_roots=[str(_root())], cwd=h.repo)
        cfg = servers.get("plugin_concord_concord")
        ctx.check(f"Halo puts the project folder in, got {cfg and cfg.env} {notices}", cfg is not None
                  and {k: cfg.env.get(k) for k in ("CONCORD_TELEMETRY_DISABLED", "CONCORD_REPO_ROOT")}
                  == {"CONCORD_TELEMETRY_DISABLED": "1", "CONCORD_REPO_ROOT": str(h.repo)} and notices == []
                  and cfg.command == "concord-mcp")
    hooks = json.loads((_root() / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    got = {ev: [x["command"] for e in hooks[ev] for x in e["hooks"]] for ev in hooks}
    off = "CONCORD_TELEMETRY_DISABLED=1 "
    ctx.check(f"Concord's four hook commands, telemetry off, got {got}", got == {
        "UserPromptSubmit": [off + "concord inbox observe"],
        "PostToolUse": [off + "concord inbox drain --from-hook --format post-tool-use"],
        "Stop": [off + "concord inbox drain --from-hook --format stop"],
        "SessionEnd": [off + "concord inbox observe"]})


def _on(h, ctx) -> None:
    code, out, err = h.cli("install", "concord")
    ctx.check(f"installed by id from the shipped folder, off, got {code} {out!r} {err!r}", code == 0
              and out.startswith("installed concord 1.0.0 at ") and "(disabled)" in out.splitlines()[0])
    code, out, err = h.cli("enable", "concord", "--grant", "hooks", "--grant", "mcp:concord")
    ctx.check(f"enabled with the two grants, got {code} {err!r}", code == 0 and "not granted" not in out)
    code, out, err = h.cli("mode", "concord", "coordinating", "on")
    ctx.check(f"coordinating on arms claimed-files, got {code} {out!r}", code == 0
              and "concord: mode coordinating on (Coordinating); armed: claimed-files" in out)


def _ask(h, pol, path):
    from halo_harness.packs import policy as P
    req = P.request(pol, "Write", {"file_path": str(path), "content": "x"}, cwd=h.repo, mode="coordinating")
    return P.ask(pol, req, keep=False, log=False)


@test
def test_the_claimed_files_policy_with_a_fake_concord(ctx: Ctx):
    from halo_harness.agent.policy_gate import said
    from halo_harness.packs import policy as P
    with PacksHome() as h:
        _on(h, ctx)
        pols = P.armed(cwd=h.repo)
        ctx.check(f"armed: claimed-files, got {[p.id for p in pols]}", [(p.pack, p.id, p.on_error) for p in pols]
                  == [("concord", "claimed-files", "allow")])
        pol = pols[0] if pols else None
        bin_dir, log = h.home / "fake-bin", h.home / "concord-calls.jsonl"
        fake_concord.install(bin_dir)
        with _path(bin_dir, FAKE_CONCORD_LOG=log):
            v = _ask(h, pol, h.repo / "claimed.txt")
            ctx.check(f"the claimed path: deny with the pack's line, got {said(v)!r}", v.action == "deny" and said(v) == LINE)
            v = _ask(h, pol, h.repo / "src" / "free.py")
            ctx.check(f"another path: allow, got {v.action} {v.reason!r}", v.action == "allow" and v.rule == "unclaimed")
            v = _ask(h, pol, h.home / "elsewhere.txt")
            ctx.check(f"outside the project: not checked, got {v.rule}", v.action == "allow" and v.rule == "outside-repo")
        calls = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
        ctx.check(f"concord check per write in the project, relative, telemetry off, got {calls}",
                  [c["argv"] for c in calls] == [["check", "claimed.txt"], ["check", "src/free.py"]]
                  and all(c["telemetry_off"] for c in calls)
                  and all(Path(c["cwd"]).resolve() == h.repo.resolve() for c in calls))
        with _path(bin_dir, FAKE_CONCORD_LOG=log, CONCORD_TASK="t-42"):
            v = _ask(h, pol, h.repo / "claimed.txt")
        last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        ctx.check(f"CONCORD_TASK is --task: its own claim allowed, got {v.action} {last['argv']}", v.action == "allow"
                  and last["argv"] == ["check", "--task", "t-42", "claimed.txt"])
        with _path(h.home / "empty-bin"):
            v = _ask(h, pol, h.repo / "claimed.txt")
        ctx.check(f"no concord on PATH: allow, got {v.action} {v.reason!r}", v.action == "allow" and v.rule == "no-concord"
                  and v.reason == "concord is not on PATH: no claim is checked")


@test
def test_doctor_says_concord_mcp_is_not_on_path(ctx: Ctx):
    with PacksHome() as h:
        _on(h, ctx)
        bin_dir = h.home / "fake-bin"
        fake_concord.install(bin_dir)
        with _path(bin_dir):
            code, out, _err = h.cli("doctor")
            got = json.loads(h.cli("doctor", "--json")[1])["problems"]
        rows = [ln.strip() for ln in out.splitlines() if ln.startswith("  [")]
        ctx.check(f"one warns row, exit 1, got {code} {rows}", code == 1 and rows == [
            "[WARN] concord: MCP server concord runs concord-mcp, which is not on PATH -> install it (the pack's README "
            "says how), or put its folder on PATH"])
        ctx.check(f"--json: check not-on-path, got {got}", [(p["pack"], p["severity"], p["check"]) for p in got]
                  == [("concord", "warns", "not-on-path")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
