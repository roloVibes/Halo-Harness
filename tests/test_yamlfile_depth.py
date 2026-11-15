"""tests.test_yamlfile_depth -- Halo 3.6.0.0 fix pass: a deeply nested YAML file is refused, it never ends the process
(halo_harness/yamlfile.py `safe_load`, the reader every pack, workflow, agent and map file goes through).

R14 moved pack and workflow files to libyaml (PyYAML's CSafeLoader). Its composer recurses in C with no recursion
check, so a small file of nested brackets (`notes: [[[[...]]]]`) in a project's `.halo/packs/<x>/pack.yaml` ended
`halo pack list` and Studio with a native stack overflow: no output, no traceback (Windows: exit 0xC00000FD). Now a
file nested deeper than `yamlfile.MAX_DEPTH` is a YAML error: the pack shows as "does not read as a YAML mapping".

1. `halo pack list` in a project holding a deeply nested pack.yaml (flow brackets, and block dashes) exits 0, names
   the pack's problem, and lists the other pack; the nesting is deep enough to overflow an 8 MB stack (Linux, macOS);
2. `safe_load` refuses a document nested past MAX_DEPTH and reads one at MAX_DEPTH, through libyaml and without it;
3. every YAML file Halo ships reads exactly as `yaml.safe_load` reads it (the guard changes nothing for real files);
4. a map file (crew/store.read) nested past MAX_DEPTH reads as None, not a RecursionError.
Run: python -m tests.test_yamlfile_depth
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
DEEP = 100_000  # past what an 8 MB C stack holds in libyaml's composer (Windows' 1-2 MB gives out near 3,000-10,000)


def _flow(depth: int) -> str:
    return "id: deep\nname: deep\nnotes: " + "[" * depth + "]" * depth + "\n"


def _block(depth: int) -> str:
    return "id: deep\nname: deep\nnotes:\n" + "- " * depth + "x\n"  # compact block sequences: `- - - x`


def _pack_list(pack_text: str) -> "tuple[int, str]":
    with tempfile.TemporaryDirectory() as tmp:
        home, proj = Path(tmp) / "home", Path(tmp) / "proj"
        home.mkdir()
        for name, text in (("deep", pack_text), ("plain", "id: plain\nname: plain\nversion: 1.0.0\n")):
            d = proj / ".halo" / "packs" / name
            d.mkdir(parents=True)
            (d / "pack.yaml").write_text(text, encoding="utf-8")
        env = dict(os.environ, BRIDGE_TEST_HOME=str(home), HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9",
                   PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-P", "-m", "halo_harness", "pack", "list"], cwd=str(proj), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        return p.returncode, (p.stdout or "") + (p.stderr or "")


@test
def test_pack_list_survives_a_deeply_nested_flow_pack_yaml(ctx: Ctx):
    rc, out = _pack_list(_flow(DEEP))
    ctx.check(f"halo pack list exits 0 and names both packs (rc={rc}, tail={out[-400:]!r})",
              rc == 0 and "deep" in out and "plain" in out)


@test
def test_pack_list_survives_a_deeply_nested_block_pack_yaml(ctx: Ctx):
    rc, out = _pack_list(_block(DEEP))
    ctx.check(f"halo pack list exits 0 and names both packs (rc={rc}, tail={out[-400:]!r})",
              rc == 0 and "deep" in out and "plain" in out)


@test
def test_safe_load_refuses_past_max_depth_and_reads_at_it(ctx: Ctx):
    from halo_harness import yamlfile
    n = yamlfile.MAX_DEPTH
    ok_flow = "a: " + "[" * (n - 1) + "]" * (n - 1)  # the top mapping is one level
    for label, loader in (("libyaml", yamlfile._LOADER), ("pure", yaml.SafeLoader)):
        old = yamlfile._LOADER
        yamlfile._LOADER = loader
        try:
            got = yamlfile.safe_load(ok_flow)
            ctx.check(f"{label}: depth {n} reads", isinstance(got, dict))
            for kind, text in (("flow", "a: " + "[" * n + "]" * n), ("block", _block(n + 1)),
                               ("deep flow", _flow(5000))):
                try:
                    yamlfile.safe_load(text)
                    ctx.check(f"{label} {kind}: refused", False)
                except yaml.YAMLError as e:
                    ctx.check(f"{label} {kind}: refused naming the depth ({e})", "deep" in str(e))
        finally:
            yamlfile._LOADER = old


@test
def test_every_shipped_yaml_reads_as_yaml_safe_load_reads_it(ctx: Ctx):
    from halo_harness import yamlfile
    files = sorted((ROOT / "halo_harness").rglob("*.yaml")) + sorted((ROOT / "halo_harness").rglob("*.yml"))
    ctx.check(f"found the shipped YAML files ({len(files)})", len(files) > 20)
    bad = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        try:
            want = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if yamlfile.safe_load(text) != want:
            bad.append(f.name)
    ctx.check(f"same data for every file, differing: {bad[:5]}", bad == [])


@test
def test_a_deep_map_file_reads_as_none(ctx: Ctx):
    from halo_harness.crew import store
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "deep.yaml"
        p.write_text("format: map/1\nname: deep\nboxes: " + "[" * 5000 + "]" * 5000 + "\n", encoding="utf-8")
        try:
            got = store.read(p)
        except RecursionError:
            got = "RecursionError"
        ctx.check(f"store.read gives None, got {got!r}", got is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
