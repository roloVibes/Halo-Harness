"""tests.test_pack_mode -- a pack's runtime mode file (Halo 3.3.10.0 R1; packs/mode_state.py, ext/mode.py,
packs/cli_policy.py; docs/EXTENSION_API.md "Policy hooks", draft):

1. `set_mode` on writes `~/.halo/packs/.data/<id>/mode.json` ({mode, since, by, armed, note}) and arms the policies
   whose when.modes name the mode; off disarms them; a second mode in its place disarms the first one's;
2. a mode or a policy the manifest does not declare is one line naming the entry and nothing is written; an
   unknown pack is the usual no-pack line;
3. every change is the pack's `mode` event in its events log;
4. `ext.set_mode` / `ext.current_mode`: [] and the mode, `by: pack:<id>`, one line for an undeclared mode;
5. `halo pack mode` and `halo pack policy arm | disarm | status` in text and JSON, exit codes;
6. `halo pack doctor` names a mode or an armed policy mode.json holds that the manifest does not declare.
Run: python -m tests.test_pack_mode
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TWO_MODES = """  modes:
    - {id: fenced, label: Fenced}
    - {id: open, label: Open}
"""


def _two_modes(h):
    """The fixture with a second mode, `open`, that arms nothing."""
    src = h.source("policy-fence")
    text = (src / "pack.yaml").read_text(encoding="utf-8")
    (src / "pack.yaml").write_text(text.replace("  modes:\n    - {id: fenced, label: Fenced}\n", TWO_MODES), encoding="utf-8")
    return src


@test
def test_set_mode_writes_the_record_and_arms(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    from halo_harness.packs.events_log import since
    with PacksHome() as h:
        h.install(_two_modes(h))
        ctx.check("no record yet: the empty one", M.read("policy-fence") == M.empty() and not M.mode_path("policy-fence").exists())
        ok, lines = M.set_mode("policy-fence", "fenced", True, by="cli", note="the release week")
        rec = json.loads(M.mode_path("policy-fence").read_text(encoding="utf-8"))
        ctx.check(f"on: the record, got {rec}", ok and rec["mode"] == "fenced" and rec["armed"] == ["fence"] and rec["by"] == "cli"
                  and rec["note"] == "the release week" and str(rec["since"]).endswith("Z"))
        ctx.check(f"the line names the mode, its label and what it armed, got {lines}",
                  lines[0] == "policy-fence: mode fenced on (Fenced); armed: fence" and "halo pack enable policy-fence --grant hooks" in lines[1])
        ctx.check("it lives in the pack's data folder", M.mode_path("policy-fence") == h.packs / ".data" / "policy-fence" / "mode.json")
        ok, lines = M.set_mode("policy-fence", "open", True, by="cli")
        ctx.check(f"another mode in its place disarms the first one's policy, got {lines} {M.read('policy-fence')}",
                  ok and M.read("policy-fence")["mode"] == "open" and M.read("policy-fence")["armed"] == []
                  and lines == ["policy-fence: mode open on (Open), was fenced; armed: none"])
        ok, lines = M.set_mode("policy-fence", "fenced", False, by="cli")
        ctx.check(f"off for a mode that is not on: nothing changed, got {lines}", ok and "is not on (the mode now: open)" in lines[0])
        M.set_mode("policy-fence", "fenced", True, by="cli")
        ok, lines = M.set_mode("policy-fence", "fenced", False, by="cli")
        ctx.check(f"off: the mode and its policies, got {lines}", ok and lines == ["policy-fence: mode fenced off; disarmed: fence"]
                  and M.read("policy-fence")["mode"] is None and M.read("policy-fence")["armed"] == [])
        rows = since("policy-fence:mode")
        ctx.check(f"every change is a mode event, got {[r['data']['change'] for r in rows]}",
                  [r["data"]["change"] for r in rows] == ["mode fenced on", "mode open on", "mode fenced on", "mode fenced off"]
                  and rows[0]["data"] == {"change": "mode fenced on", "mode": "fenced", "armed": ["fence"], "by": "cli"})


@test
def test_what_the_manifest_does_not_declare_is_one_line(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    with PacksHome() as h:
        h.install(h.source("policy-fence"))
        ok, lines = M.set_mode("policy-fence", "audit", True)
        ctx.check(f"an undeclared mode: one line naming contributes.modes, got {lines}",
                  not ok and lines == ["policy-fence declares no mode 'audit' (contributes.modes: fenced)"])
        ok, lines = M.arm("policy-fence", "gate")
        ctx.check(f"an undeclared policy: one line naming contributes.policy, got {lines}",
                  not ok and lines == ["policy-fence declares no policy 'gate' (contributes.policy: fence)"])
        ok2, lines2 = M.disarm("policy-fence", "gate")
        ctx.check("disarm says the same", not ok2 and lines2 == lines)
        ctx.check("nothing was written", not M.mode_path("policy-fence").exists())
        ok, lines = M.set_mode("no-such-pack", "x", True)
        ctx.check(f"an unknown pack: the no-pack line, got {lines}", not ok and lines[0].startswith("no pack 'no-such-pack' here"))
        h.install(h.source())
        ok, lines = M.set_mode("doc-review", "fenced", True)
        ctx.check(f"a pack with no modes: 'none', got {lines}", not ok and lines == ["doc-review declares no mode 'fenced' (contributes.modes: none)"])


@test
def test_arm_and_disarm_name_one_policy(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    with PacksHome() as h:
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        ok, lines = M.arm("policy-fence", "fence")
        ctx.check(f"armed, and said when it is asked, got {lines}", ok and lines == [
            "policy-fence: policy fence armed", "it is asked while mode fenced is on (the mode now: none)"])
        ctx.check("the record holds it, the mode untouched", M.read("policy-fence")["armed"] == ["fence"] and M.read("policy-fence")["mode"] is None)
        ctx.check("arming it again: already", M.arm("policy-fence", "fence")[1] == ["policy-fence: policy fence is already armed"])
        ok, lines = M.disarm("policy-fence")
        ctx.check(f"disarm with no name: every armed one, got {lines}", ok and lines == ["policy-fence: disarmed fence"])
        ctx.check("nothing armed: nothing changed", M.disarm("policy-fence")[1] == ["policy-fence: no policy is armed; nothing changed"])


@test
def test_the_ext_door(ctx: Ctx):
    import halo_harness.ext as ext
    from halo_harness.packs import mode_state as M
    with PacksHome() as h:
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        ctx.check("no mode yet", ext.current_mode("policy-fence") is None)
        ctx.check("set_mode: [] when written", ext.set_mode("policy-fence", "fenced") == [])
        ctx.check("current_mode reads it", ext.current_mode("policy-fence") == "fenced")
        ctx.check(f"by the pack itself, got {M.read('policy-fence')['by']}", M.read("policy-fence")["by"] == "pack:policy-fence")
        ctx.check("an undeclared mode: one line", ext.set_mode("policy-fence", "audit") == [
            "policy-fence declares no mode 'audit' (contributes.modes: fenced)"])
        ctx.check("off: []", ext.set_mode("policy-fence", "fenced", on=False) == [] and ext.current_mode("policy-fence") is None)
        try:
            ext.set_mode("Bad--Id", "x")
            raised = ""
        except ValueError as e:
            raised = str(e)
        ctx.check(f"a bad pack id raises like every ext call, got {raised!r}", bool(raised))


@test
def test_the_cli_verbs(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        code, out, err = h.cli("mode", "policy-fence", "fenced", "on", "--note", "release week")
        ctx.check(f"halo pack mode ... on: exit 0 and the line, got {code} {out!r} {err!r}",
                  code == 0 and out.strip() == "policy-fence: mode fenced on (Fenced); armed: fence")
        code, out, err = h.cli("mode", "policy-fence", "audit", "on")
        ctx.check(f"an undeclared mode: exit 1, one line on stderr, got {code} {err!r}",
                  code == 1 and out == "" and err.strip() == "halo pack: policy-fence declares no mode 'audit' (contributes.modes: fenced)")
        code, out, _ = h.cli("policy", "status", "--json")
        rows = json.loads(out)["packs"]
        ctx.check(f"status --json: the pack, its mode, the policy asked now, got {rows}", code == 0 and rows[0]["id"] == "policy-fence"
                  and rows[0]["mode"]["mode"] == "fenced" and rows[0]["policies"][0]["state"] == "armed, asked now")
        code, out, _ = h.cli("policy", "status")
        lines = out.splitlines()  # 3.3.10.0 R2: the process line (running once a session process armed it, else not)
        ctx.check(f"status in text, got {out!r}", code == 0 and lines[:2] == [
            "policy-fence 0.1.0 (runs here): mode fenced", "  fence: armed, asked now"] and len(lines) == 3
            and re.fullmatch(r"    process (running [(]pid [0-9]+[)]|not running); verdicts: none yet "
                             r"[(]halo pack policy log policy-fence[)]", lines[2]))
        code, out, _ = h.cli("policy", "disarm", "policy-fence", "fence", "--json")
        ctx.check(f"disarm --json, got {out!r}", code == 0 and json.loads(out) == {"ok": True, "lines": ["policy-fence: disarmed fence"]})
        code, out, _ = h.cli("policy", "status")
        ctx.check(f"not armed: the command that arms it, got {out!r}",
                  "  fence: not armed (halo pack policy arm policy-fence fence)" in out.splitlines())
        code, out, _ = h.cli("policy", "arm", "policy-fence", "fence")
        ctx.check("arm: exit 0", code == 0 and out.startswith("policy-fence: policy fence armed"))
        code, _out, err = h.cli("policy", "arm", "policy-fence")
        ctx.check(f"arm without the policy: usage, exit 2, got {code} {err!r}", code == 2 and "halo pack policy arm <pack> <policy>" in err)
        from halo_harness.packs.grants import disable
        disable("policy-fence")
        code, out, _ = h.cli("policy", "status")
        ctx.check(f"a disabled pack: armed, not asked, and why, got {out!r}", "(disabled): mode fenced" in out
                  and "armed, not asked: the pack does not run here (halo pack enable policy-fence --grant hooks)" in out)
        code, out, _ = h.cli("mode", "policy-fence", "fenced", "off")
        ctx.check("off: exit 0", code == 0 and out.strip() == "policy-fence: mode fenced off; disarmed: fence")
    with PacksHome() as h:
        h.install(h.source())
        code, out, _ = h.cli("policy", "status")
        ctx.check(f"a pack without policies or modes is not listed, got {out!r}", code == 0
                  and out.strip() == "No pack here declares a policy hook or a mode.")


@test
def test_doctor_names_what_mode_json_holds_and_the_manifest_does_not(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    with PacksHome() as h:
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        path = M.mode_path("policy-fence")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mode": "ghost", "armed": ["fence", "gone"]}), encoding="utf-8")
        code, out, _ = h.cli("doctor")
        ctx.check(f"two warnings, each with its fix, got {out!r}", code == 1
                  and "[WARN] policy-fence: mode.json names mode 'ghost', which contributes.modes does not declare" in out
                  and "[WARN] policy-fence: mode.json arms policy 'gone', which contributes.policy does not declare -> "
                      "halo pack policy disarm policy-fence gone" in out and "'fence'" not in out)
        M.set_mode("policy-fence", "fenced", True)
        M.disarm("policy-fence", "fence")
        code, out, _ = h.cli("doctor")
        ctx.check(f"after the doors rewrote it: the stray armed id stays named, the mode is fine, got {out!r}",
                  "mode 'ghost'" not in out and "arms policy 'gone'" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
