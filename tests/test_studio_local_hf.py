"""tests.test_studio_local_hf -- Halo 3.3.5.0 R5 "Hugging Face local models, controlled": Studio's Local -> Hugging Face
in headless Chrome through tests/helpers/studio_local_hf.py (skipped without one), over R1's seeded home plus the fake
hub (127.0.0.1:0, HF_ENDPOINT) and the fake llama-server (huggingface.llama_server_bin). No real hub, no real server,
no model call:

1. the page is built; Add folder writes huggingface.model_dirs (its title the `halo local add` line);
2. Library -> a hub row's Download: the licence card first (its line, the files, the folder), the progress bar, then
   "on disk in <folder>"; the Hugging Face page lists the model with its fit meter;
3. Serve: each flag with its source (the window and -ngl from the planner on box's card), the command line, Start;
   the row says which server serves it; the Hosts card (Stop, Log; a server Halo did not start has Stop disabled
   with why); `hf:local/<model>` in Models; Log's tail; Stop;
4. Delete with the uses card (a role names it: Delete anyway), the row and the file gone.
Run: python -m tests.test_studio_local_hf
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
MODEL = "Qwen3.8-27B-Q4_K_M"


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Hugging Face page checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_local_hf"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=480, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_page_and_add_folder(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"built, not framed; empty at first, got {got.get('built')} {got.get('none')}", got.get("built") and got.get("none"))
    ctx.check(f"Add folder writes model_dirs, its title the CLI line, got {got.get('config_dirs')} {got.get('add_title')}",
              got.get("config_dirs") == [got.get("dir")] and got.get("add_title") == f"halo local add {got.get('dir')}")


@test
def test_download_from_the_library_licence_first_then_on_disk(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Download's title is the CLI line, got {got.get('dl_title')!r}",
              got.get("dl_text") == "Download" and got.get("dl_title") == "halo local download unsloth/Qwen3.8-27B-GGUF")
    ctx.check(f"the licence card before a byte moves, got {got.get('licence')!r} {got.get('files')!r} {got.get('before_bytes')}",
              "licence apache-2.0" in got.get("licence", "") and "Qwen3.8-27B-Q4_K_M.gguf" in got.get("files", "")
              and got.get("before_bytes") == 0 and got.get("dl_dir") == got.get("dir"))
    ctx.check(f"the bar moved, then on disk in the folder, got {got.get('moving')} {got.get('ondisk')!r}",
              0 < float(got.get("moving") or 0) < 100 and got.get("ondisk") == f"on disk in {got.get('dir')}")
    kind, level, why = (got.get("hf_row") or ["", "", ""])[:3]
    ctx.check(f"the page lists it with its fit, got {got.get('hf_row')}", kind == "gguf" and level in ("fits", "tight") and "weights" in why)


@test
def test_serve_hosts_models_log_stop(ctx: Ctx):
    got = _got(ctx)
    flags = {f[0]: f for f in got.get("flags") or []}
    ctx.check(f"the flags with their sources, got {flags}", flags.get("window", [0, 0, ""])[1] == "40960"
              and "box's card" in flags["window"][2] and flags.get("ngl", [0, 0, ""])[1] == "37" and "every layer" in flags["ngl"][2]
              and flags.get("parallel", [0, 0, ""])[1] == "1")
    ctx.check(f"the command line, Start's title, got {got.get('argv')!r}", " -c 40960 -ngl 37 -np 1 " in got.get("argv", "")
              and "--host 127.0.0.1" in got.get("argv", "") and got.get("go_title", "").startswith("halo local serve "))
    ctx.check(f"started, the row says who serves it, got {got.get('said')!r} {got.get('served')!r}",
              f"hf:local/{MODEL}" in got.get("said", "") and str(got.get("served", "")).startswith("served by llama-")
              and got.get("default_title") == f"model = hf:local/{MODEL} (Setup's save)")
    name, kind, model_line, stop_title = (got.get("host_card") or ["", "", "", ""])[:4]
    ctx.check(f"a Hosts card with Stop, got {got.get('host_card')}", name.startswith("llama-") and kind == "llama-server"
              and MODEL in model_line and stop_title.startswith(f"halo local stop {name}"))
    ctx.check(f"a server Halo did not start: Stop disabled with why, got {got.get('not_ours')}",
              got.get("not_ours") and got["not_ours"][0] is True and "did not start" in got["not_ours"][1])
    ctx.check(f"hf:local/<model> in Models under the server, got {got.get('models_row')}", got.get("models_row") == [name])
    ctx.check(f"Log's tail, got {got.get('log')}", any("offloaded 37/37" in ln for ln in got.get("log") or []))
    ctx.check(f"Stop ended it, got {got.get('after_stop')}", got.get("after_stop") == [])


@test
def test_delete_with_the_uses_card(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the uses card names the role, got {got.get('uses')!r} {got.get('go')}", "`reviewer` role" in got.get("uses", "")
              and (got.get("go") or [""])[0] == "Delete anyway" and got["go"][1].endswith("--force"))
    ctx.check(f"the row and the file gone, got {got.get('gone')} {got.get('on_disk')}", got.get("gone") is True and got.get("on_disk") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
