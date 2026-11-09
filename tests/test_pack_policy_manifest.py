"""tests.test_pack_policy_manifest -- `contributes.policy` and `contributes.modes` (Halo 3.3.10.0 R1;
packs/manifest_policy.py, schemas/pack_yaml.py, pack.schema.json, packs/policy_views.py; docs/EXTENSION_API.md
"Policy hooks", draft):

1. the fixture policy-fence validates and installs; its command has ${halo_python} and ${CLAUDE_PLUGIN_ROOT} put in;
2. every bad value is one line naming the entry (run outside the pack or missing, a tool Halo does not have with
   the closest one, a mode the pack does not declare, on_error, impact, redact, after, ids) and install refuses it;
3. a policy needs the hooks permission (requested; doctor's not-granted row until granted);
4. the YAML shape, the JSON schema twin and field_help carry both keys; a 1.0 pack without them is untouched;
5. `halo pack inspect` lists the policies and the modes; `halo pack doctor` flags a policy whose run is missing.
Run: python -m tests.test_pack_policy_manifest
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
GOOD = """  policy:
    - id: fence
      run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/policy/fence.py"]
      when: {tools: [Write, Edit], modes: [fenced]}
      impact: high
      on_error: deny
"""


def _lines(h, policy_block: str, *, perms: str = "[hooks]", modes: str = "    - {id: fenced, label: Fenced}\n") -> list:
    from halo_harness.packs.discover import read_pack
    src = h.source("policy-fence")
    text = (src / "pack.yaml").read_text(encoding="utf-8").replace(GOOD, policy_block)
    text = text.replace("    - {id: fenced, label: Fenced}\n", modes).replace("permissions: [hooks]", f"permissions: {perms}")
    (src / "pack.yaml").write_text(text, encoding="utf-8")
    return read_pack(src, "source", folder_is_id=False).problems


@test
def test_the_fixture_validates_installs_and_runs_from_its_folder(ctx: Ctx):
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs.discover import find, read_pack
    pack = read_pack(fixture("policy-fence"), "source")
    ctx.check(f"no problems, got {pack.problems}", pack.problems == [])
    ctx.check("one policy, one mode", MP.ids(MP.policies_of(pack.manifest)) == ["fence"] and MP.ids(MP.modes_of(pack.manifest)) == ["fenced"])
    with PacksHome() as h:
        h.install(h.source("policy-fence"))
        installed = find("policy-fence", cwd=h.repo)
        argv = MP.run_argv(MP.entry(installed.manifest, "fence"), installed.root)
        ctx.check(f"${{halo_python}} is Halo's Python, the script the pack's file, got {argv}",
                  argv[0] == sys.executable and Path(argv[1]) == installed.root / "policy" / "fence.py")
        e = {"id": "x", "run": "${halo_python} policy/fence.py"}
        ctx.check("one string is split like a shell line; a bare pack path is the pack's file",
                  MP.run_argv(e, installed.root) == [sys.executable, str(installed.root / "policy" / "fence.py")]
                  and MP.script_rel(e["run"]) == ("policy/fence.py", ""))
        ctx.check("the policy needs hooks", ("hooks", "policy fence") in MP.needs(installed.manifest))


@test
def test_every_bad_value_is_one_line_naming_the_entry(ctx: Ctx):
    bad = """  policy:
    - id: fence
      run: ["${halo_python}", "/etc/fence.py"]
      when: {tools: [Wirte, "mcp__lint__check", "*"], modes: [audit]}
      impact: huge
      on_error: maybe
      redact: ["A=B", OK_NAME]
      after: "yes"
    - id: fence
      run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/../outside.py"]
    - id: gate
      run: ["${halo_python}", "policy/missing.py"]
    - id: bad--id
      run: ["${halo_python}"]
"""
    with PacksHome() as h:
        got = _lines(h, bad, modes="    - {id: fenced, label: Fenced}\n    - {id: fenced}\n")
        want = [
            "contributes.modes[1].id 'fenced' is used twice",
            "contributes.policy[1].id 'fence' is used twice",
            "contributes.policy[3].id 'bad--id' is not a name (letters, digits, - and _, no --)",
            "contributes.policy[0].run: '/etc/fence.py' is outside the pack folder (a command in the pack: ${CLAUDE_PLUGIN_ROOT}/<path>)",
            "contributes.policy[0].when.tools: 'Wirte' is not a tool Halo has (closest: Write); a tool name, mcp__<server>__<tool> or *",
            "contributes.policy[0].when.modes: 'audit' is not one of contributes.modes (fenced)",
            "contributes.policy[0].on_error 'maybe' is not one of allow, deny (allow when left out)",
            "contributes.policy[0].impact 'huge' is not one of low, medium, high (medium when left out)",
            "contributes.policy[0].redact: 'A=B' is not an environment variable name (the name, never its value)",
            "contributes.policy[0].after: true or false",
            "contributes.policy[1].run: '${CLAUDE_PLUGIN_ROOT}/../outside.py' is outside the pack folder (a command in the pack: ${CLAUDE_PLUGIN_ROOT}/<path>)",
            "contributes.policy[2].run: policy/missing.py is not in the pack",
            "contributes.policy[3].run: ${halo_python} needs the pack file it runs after it",
        ]
        missing = [w for w in want if w not in got]
        ctx.check(f"each line, naming the entry; missing {missing}; got {got}", not missing)
        ctx.check("the shape check reads after: a boolean", any(ln.startswith("contributes.policy[0].after") for ln in got))
        ctx.check("an mcp tool and * are fine", not any("mcp__lint__check" in ln or "'*'" in ln for ln in got))
        ok, lines = _install(h)
        ctx.check(f"install refuses it with those lines, got {ok} {lines[:2]}", not ok and lines[0].startswith("policy-fence: pack.yaml: "))
        got = _lines(h, GOOD, perms="[]")
        ctx.check(f"no hooks requested: one line, got {got}", got == ["permissions: policy fence needs 'hooks', which the pack does not request"])
        got = _lines(h, "  policy:\n    - {id: x, run: [\"${halo_python}\", \"policy/fence.py\"], colour: red}\n")
        ctx.check(f"an unknown key: the shape check's line with the closest one, got {got}", any("colour" in ln for ln in got))


def _install(h):
    from halo_harness.packs.install import install
    return install(str(h.sources / "policy-fence"), cwd=h.repo)


@test
def test_the_shape_the_json_twin_and_field_help(ctx: Ctx):
    from halo_harness import field_help
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.schemas.pack_yaml import CONTRIBUTION_KEYS, MODE_KEYS, POLICY_KEYS
    ctx.check("contributes has policy and modes", tuple(CONTRIBUTION_KEYS[CONTRIBUTION_KEYS.index("policy"):][:2]) == ("policy", "modes"))  # later keys follow them
    ctx.check("one key list in both modules", POLICY_KEYS == MP.POLICY_KEYS and MODE_KEYS == MP.MODE_KEYS)
    schema = json.loads((REPO / "halo_harness" / "packs" / "schema" / "pack.schema.json").read_text(encoding="utf-8"))
    contributes = schema["properties"]["contributes"]["properties"]
    ctx.check("the JSON schema's contributes has both", contributes["policy"]["items"]["$ref"] == "#/$defs/policy"
              and contributes["modes"]["items"]["$ref"] == "#/$defs/mode")
    ctx.check("its $defs.policy holds the same keys", tuple(schema["$defs"]["policy"]["properties"]) == POLICY_KEYS
              and schema["$defs"]["policy"]["properties"]["on_error"]["enum"] == list(MP.ON_ERROR)
              and schema["$defs"]["policy"]["properties"]["impact"]["enum"] == list(MP.IMPACT))
    ctx.check("its $defs.mode holds the same keys", tuple(schema["$defs"]["mode"]["properties"]) == MODE_KEYS)
    ctx.check("field_help has a 3.3.10.0 line for each (stable since R2)", "3.3.10.0" in field_help.PACK["contributes.policy"]
              and "3.3.10.0" in field_help.PACK["contributes.modes"] and "draft" not in field_help.PACK["contributes.policy"])
    live = MP.tool_names()  # the contract: every tool class loaded in this process, read now (never a frozen list)
    ctx.check("the core names are in it", set(MP.KNOWN_TOOLS) <= live)
    refused = sorted(n for n in live if not MP.tool_known(n))
    ctx.check(f"when.tools takes every tool Halo has loaded, refused {refused}", not refused)
    ctx.check("and *, an MCP tool, a connector; not a made-up name", MP.tool_known("*") and MP.tool_known("mcp__lint__check")
              and MP.tool_known("connector__drive") and not MP.tool_known("Wirte"))
    from halo_harness import preflight  # noqa: F401  (a tool class outside halo_harness/tools/, loaded by other modules)
    ctx.check("a tool class another module loads (PreflightProbe) is a tool name too",
              "PreflightProbe" in MP.tool_names() and MP.tool_known("PreflightProbe"))


@test
def test_a_pack_without_them_is_untouched(ctx: Ctx):
    from halo_harness.packs import policy as P
    from halo_harness.packs.discover import read_pack
    pack = read_pack(fixture("doc-review"), "source")
    ctx.check("the reference pack (halo_api 1.0) still validates", pack.problems == [])
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["hooks", "bash", "mcp:lint"])
        code, out, _ = h.cli("inspect", "doc-review", "--json")
        data = json.loads(out)
        ctx.check("inspect: no policy block, no policies or modes offered", data["policy"] is None
                  and data["offers"]["policies"] == [] and data["offers"]["modes"] == [])
        ctx.check("no policy is armed anywhere", P.armed(cwd=h.repo) == [])
        code, out, _ = h.cli("inspect", "doc-review")
        ctx.check("the text has no policy lines", "policy hooks" not in out)


@test
def test_inspect_lists_them_and_doctor_flags_a_missing_run(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    with PacksHome() as h:
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        M.set_mode("policy-fence", "fenced", True)
        code, out, _ = h.cli("inspect", "policy-fence")
        lines = out.splitlines()
        for want in ("  policy hooks: fence", "  modes: fenced", "  mode fenced (Fenced): on",
                     "  policy fence: tools Write, Edit; modes fenced; impact high; on_error deny",
                     "    run: ${halo_python} ${CLAUDE_PLUGIN_ROOT}/policy/fence.py", "    armed, asked now",
                     "  hooks (policy fence): granted"):
            ctx.check(f"inspect has {want!r}", want in lines)
        code, out, _ = h.cli("inspect", "policy-fence", "--json")
        pol = json.loads(out)["policy"]["policies"][0]
        ctx.check(f"--json: the policy with its state, got {pol}", pol["id"] == "fence" and pol["on_error"] == "deny"
                  and pol["tools"] == ["Write", "Edit"] and pol["state"] == "armed, asked now")
        code, out, _ = h.cli("doctor")
        ctx.check(f"a healthy pack: no problem, got {out!r}", code == 0)
        (h.packs / "policy-fence" / "policy" / "fence.py").unlink()
        code, out, _ = h.cli("doctor")
        ctx.check(f"its run gone: doctor names the entry, got {out!r}", code == 1
                  and "contributes.policy[0].run: policy/fence.py is not in the pack" in out)
    with PacksHome() as h:
        h.install(h.source("policy-fence"), enable=True)
        code, out, _ = h.cli("doctor")
        ctx.check(f"enabled without hooks: the not-granted row, got {out!r}",
                  "[WARN] policy-fence: policy fence does not run: hooks is not granted -> halo pack enable policy-fence --grant hooks" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
