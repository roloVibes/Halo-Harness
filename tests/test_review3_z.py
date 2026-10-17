"""tests.test_review3_z -- pins for fix pass round Z (the follow-ups the
3.0.1.0 review fix pass left open), non-TUI items:

  * Z1  a design turn sends its prompt on stdin, never in argv
  * Z2  /clear on a `cx:` session closes the codex bridge
  * Z3  gpg runs with the provider keys stripped
  * Z5  Org layouts persist under a file name NTFS accepts
  * Z6  the model-table ingest keeps every other section

Z8/Z9/Z10 are in tests/test_review3_z3.py; the TUI items (Z4, Z7) in _z2.

Run: python -m tests.test_review3_z
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _FakePopen:
    """A child that reads all of stdin before it writes (as `halo -p` does)."""
    last = None

    def __init__(self, cmd, **kw):
        _FakePopen.last = self
        self.cmd, self.kw, self.returncode = cmd, kw, 0
        self.got, self._closed = [], threading.Event()
        self.stdin = SimpleNamespace(write=self.got.append, close=self._closed.set)
        self.stdout = self._lines()

    def _lines(self):
        self._closed.wait(10)
        yield json.dumps({"type": "result", "result": "ok", "total_cost_usd": 0.01}) + "\n"

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


@test
def test_z1_a_300kb_design_prompt_goes_on_stdin_not_argv(ctx: Ctx):
    from halo_harness.design import session as S
    from halo_harness.design.store import Project
    p = Project.create("Big Prompt", model="or:v/eyes")
    prompt = "make it bigger " + ("x" * 300_000)
    real = S.subprocess.Popen
    S.subprocess.Popen = _FakePopen
    try:
        r = S.run_turn(p, prompt, registered=set(), entries={}, timeout=20)
    finally:
        S.subprocess.Popen = real
    fake = _FakePopen.last
    ctx.check("the child started and the turn finished", r["code"] == 0 and r["text"] == "ok")
    ctx.check("no argv entry carries the prompt", all(len(str(a)) < 4096 and "make it bigger" not in str(a) for a in fake.cmd))
    ctx.check("print mode with no PROMPT argument (-p is followed by a flag)", fake.cmd[fake.cmd.index("-p") + 1].startswith("--"))
    ctx.check("stdin is a pipe", fake.kw.get("stdin") is S.subprocess.PIPE)
    ctx.check("the whole prompt arrived on stdin", "".join(fake.got) == prompt)
    ctx.check("the log keeps the prompt as asked", p.history()[-1]["prompt"] == prompt)


@test
def test_z1_the_stdin_prompt_is_capped_in_bytes_and_a_runner_can_take_it(ctx: Ctx):
    from halo_harness.design import session as S
    from halo_harness.design.store import Project
    big = "é" * (S.MAX_PROMPT_BYTES)  # two bytes each: twice the cap
    capped = S._stdin_prompt(big)
    ctx.check("capped at MAX_PROMPT_BYTES on a whole character",
              len(capped.encode("utf-8")) <= S.MAX_PROMPT_BYTES and set(capped) == {"é"})
    ctx.check("a prompt under the cap is untouched", S._stdin_prompt("hello") == "hello")
    seen = {}

    def runner(cmd, cwd, env, on_line, stdin=None):
        seen["cmd"], seen["stdin"] = cmd, stdin
        return 0
    p = Project.create("Runner Stdin")
    S.run_turn(p, "a hero", registered=set(), entries={}, runner=runner)
    ctx.check("a runner that takes stdin= gets the prompt", seen["stdin"] == "a hero" and "a hero" not in seen["cmd"])


@test
def test_z2_clear_closes_a_live_cx_bridge(ctx: Ctx):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    proj = Path(tempfile.mkdtemp(prefix="z2-proj-"))
    model = "or:test/model"
    s = Session(cwd=proj, model_ref=parse_model_ref(model),
                model_profile=ModelProfile(context_tokens=200_000, max_output_tokens=8192), creds=None,
                state_dir=Path(tempfile.mkdtemp(prefix="z2-state-")), model_label=model,
                session_context=SessionContext(cwd=proj, model_label=model), max_turns=4,
                permission_engine=PermissionEngine(mode="auto", cwd=proj))
    closed = []
    s._cx_state = SimpleNamespace(bridge=SimpleNamespace(close=lambda: closed.append(True)), thread_id="old-thread")
    old_id = s.log.session_id
    s.clear()
    ctx.check("the codex bridge was closed", closed == [True])
    ctx.check("no cx state survives /clear", getattr(s, "_cx_state", None) is None)
    ctx.check("a new session log", s.log.session_id != old_id)
    s.clear()
    ctx.check("a second /clear with no cx state is fine", closed == [True])


@test
def test_z3_gpg_runs_without_provider_keys(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    sig = Path(tempfile.mkdtemp(prefix="z3-")) / "a.tar.gz.asc"
    sig.write_text("sig", encoding="utf-8")
    seen = {}

    def runner(argv, **kw):
        seen["argv"], seen["env"] = argv, kw.get("env")
        return SimpleNamespace(returncode=2, stdout="", stderr="")
    saved = (inst.RELEASE_KEY_FINGERPRINT, inst.shutil.which, os.environ.get("OPENROUTER_API_KEY"),
             os.environ.get("DATABRICKS_TOKEN"))
    inst.RELEASE_KEY_FINGERPRINT = "A" * 40
    inst.shutil.which = lambda name: "/usr/bin/" + name
    os.environ["OPENROUTER_API_KEY"] = "z3-or-value"
    os.environ["DATABRICKS_TOKEN"] = "z3-dbx-value"
    try:
        status, _ = inst.verify_signature(sig.with_suffix(""), sig, runner=runner)
    finally:
        inst.RELEASE_KEY_FINGERPRINT, inst.shutil.which = saved[0], saved[1]
        for k, v in (("OPENROUTER_API_KEY", saved[2]), ("DATABRICKS_TOKEN", saved[3])):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    env = seen.get("env")
    ctx.check("gpg ran through the stubbed runner", seen.get("argv", [None])[0] == "gpg" and status == "unverified")
    ctx.check("gpg got an explicit environment", isinstance(env, dict) and bool(env))
    ctx.check("no provider key reaches gpg", "OPENROUTER_API_KEY" not in env and "DATABRICKS_TOKEN" not in env
              and "z3-or-value" not in env.values())


@test
def test_z5_org_layouts_use_a_file_name_without_a_colon(ctx: Ctx):
    from halo_harness.studio import model as M
    state = Path(tempfile.mkdtemp(prefix="z5-"))
    M.write_layout(state, "pc:abc-123", {"n1": {"x": 1, "y": 2}})
    files = sorted(p.name for p in M.layouts_dir(state).iterdir())
    ctx.check(f"stored as _pc-abc-123.json, got {files}", files == ["_pc-abc-123.json"])
    ctx.check("it reads back", M.read_layout(state, "pc:abc-123") == {"nodes": {"n1": {"x": 1, "y": 2}}, "tiers": {}})
    M.write_layout(state, "pc-abc-123", {"lineup": {"x": 9, "y": 9}})
    ctx.check("a lineup named pc-abc-123 keeps its own file",
              M.read_layout(state, "pc-abc-123") == {"nodes": {"lineup": {"x": 9, "y": 9}}, "tiers": {}}
              and M.read_layout(state, "pc:abc-123") == {"nodes": {"n1": {"x": 1, "y": 2}}, "tiers": {}})
    ctx.check("a lineup layout keeps its plain name", M.layout_file_name("main") == "main.json")


@test
def test_z5_an_old_colon_layout_is_read_once_and_moved_on_posix(ctx: Ctx):
    from halo_harness.studio import model as M
    if os.name == "nt":
        ctx.check("the old spelling is never consulted on Windows (it was an NTFS stream)",
                  M.read_layout(Path(tempfile.mkdtemp(prefix="z5w-")), "pc:old") == {"nodes": {}, "tiers": {}})
        return
    state = Path(tempfile.mkdtemp(prefix="z5p-"))
    d = M.layouts_dir(state)
    d.mkdir(parents=True)
    (d / "pc:old.json").write_text(json.dumps({"a": {"x": 3, "y": 4}}), encoding="utf-8")
    ctx.check("the old spelling is read", M.read_layout(state, "pc:old") == {"nodes": {"a": {"x": 3, "y": 4}}, "tiers": {}})
    names = sorted(p.name for p in d.iterdir())
    ctx.check(f"and moved to the new one, got {names}", names == ["_pc-old.json"])
    ctx.check("it still reads after the move", M.read_layout(state, "pc:old") == {"nodes": {"a": {"x": 3, "y": 4}}, "tiers": {}})


@test
def test_z6_ingest_keeps_every_other_section(ctx: Ctx):
    sys.path.insert(0, str(REPO_DIR / "tools"))
    import ingest_model_table as I
    shipped = REPO_DIR / "halo_harness" / "providers" / "model_table.json"
    tmp = Path(tempfile.mkdtemp(prefix="z6-")) / "model_table.json"
    shutil.copyfile(shipped, tmp)
    before = json.loads(tmp.read_text(encoding="utf-8"))
    before["openrouter"]["hand/added-row"] = {"family": "hand", "edit_format": "diff"}
    first = next(iter(before["databricks"]))
    before["databricks"][first]["hand_note"] = "kept"
    tmp.write_text(json.dumps(before), encoding="utf-8")
    rc = I.main(out_path=tmp)
    after = json.loads(tmp.read_text(encoding="utf-8"))
    others = [k for k in before if k not in ("openrouter", "databricks")]
    ctx.check(f"the shipped table has hand-authored sections, got {others}",
              {"anthropic_model_capabilities", "decision_only_name_patterns", "edit_hints"} <= set(others))
    ctx.check("every other section survives unchanged", rc == 0 and all(after.get(k) == before[k] for k in others))
    ctx.check("the sections keep their order", list(after)[:len(others)] == others)
    ctx.check("the host tables were recompiled", len(after["openrouter"]) > 10 and len(after["databricks"]) > 5)
    ctx.check("a hand-added row and a hand-added field are kept",
              "hand/added-row" in after["openrouter"] and after["databricks"][first].get("hand_note") == "kept")
    merged = I.merge_sections({"x": 1, "openrouter": {"a": {"k": 1, "own": 2}}}, {"openrouter": {"a": {"k": 9}}, "databricks": {}})
    ctx.check("merge_sections: report value wins, own field kept, new host appended",
              merged == {"x": 1, "openrouter": {"a": {"k": 9, "own": 2}}, "databricks": {}})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
