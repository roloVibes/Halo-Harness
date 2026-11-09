"""tests.test_engines_descriptors -- Halo 3.3.13.0 R1 deliverable 1: the descriptor table
(halo_harness/engines/descriptors.py) and the models each engine names (engines/models.py):

1. every entry is complete (id, label, url, port, routes, detect, programs, version, install, requires, where it runs,
   log, fixes, fit, tune) and says `verified: False`; the ids are the old runtime words, so a config.json that says
   `runtime: freetoken | strata | tensorfold` keeps working; every log pattern compiles and its sentence names only its
   own groups; every fit rule is `vram` or `paged-moe` with its figures;
2. the install line is the owner's, per OS (Halo never installs an engine); an OS an engine ships nothing for says so;
3. the table is the only place an engine's port, its owned_by word and its log wording live in halo_harness/;
4. the models rows: every row names an engine of the table, the old catalogs' counts and figures carried over (16
   FreeToken checkpoints, 24 Strata sets, 24 TensorFold models), and `match` finds a row from a repo, a family/set, a
   served id or a lane's model.
Run: python -m tests.test_engines_descriptors
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PKG = Path(__file__).resolve().parent.parent / "halo_harness"
KEYS = ("id", "label", "url", "what", "source", "default_port", "base_path", "health", "stats", "detect", "programs",
        "version", "install", "requires", "backends", "os", "arch", "start", "log", "fixes", "fit", "tune", "verified")


@test
def test_every_entry_is_complete(ctx: Ctx):
    from halo_harness.engines.descriptors import SEVERITY, TABLE, WORDS, get, ids, kinds
    ctx.check(f"the ids are the old runtime words, got {ids()}", ids() == ("freetoken", "strata", "tensorfold"))
    for d in TABLE.values():
        miss = [k for k in KEYS if k not in d]
        ctx.check(f"{d['id']}: every key, missing {miss}", not miss and d["verified"] is False)
        ctx.check(f"{d['id']}: a port, the /v1 base and a health route", isinstance(d["default_port"], int)
                  and d["base_path"] == "/v1" and d["health"] == "/health" and d["programs"])
        ctx.check(f"{d['id']}: detected by owned_by or /health keys", bool(d["detect"].get("owned_by") or d["detect"].get("health")))
        for word, rx, sentence, *conds in d["log"]["patterns"]:
            groups = set(re.compile(rx).groupindex)
            names = set(re.findall(r"\{(\w+)\}", sentence))
            ctx.check(f"{d['id']} {word}: a known word, its sentence names its own groups ({names - groups})",
                      word in WORDS and word in SEVERITY and names <= groups
                      and all(c[0] in groups | {"model"} for c in conds))
        ctx.check(f"{d['id']}: the fit rule and its figures", d["fit"]["rule"] in ("vram", "paged-moe")
                  and isinstance(d["fit"]["disk_bps"], float))
        ctx.check(f"{d['id']}: its fixes are for its own words", set(d["fixes"]) <= {p[0] for p in d["log"]["patterns"]}
                  | {"waiting"})
        ctx.check(f"{d['id']}: the steward kinds it can say, got {kinds(d)}", "load-result" in kinds(d)
                  and "other-error" in kinds(d))
    ctx.check("get is case-blind and None for others", get("Strata") is TABLE["strata"] and get("llama-server") is None)
    ctx.check("only Strata is supervised; every engine has a managed start",
              [d["id"] for d in TABLE.values() if (d["start"] or {}).get("supervised")] == ["strata"]
              and all(d["start"] for d in TABLE.values()))


@test
def test_the_install_line_is_the_owners_per_os(ctx: Ctx):
    from halo_harness.engines.descriptors import TABLE, install_line
    ft, st, tf = TABLE["freetoken"], TABLE["strata"], TABLE["tensorfold"]
    ctx.check("FreeToken on Linux: uv pip", install_line(ft, "linux") == 'uv pip install "freetoken[accel]"')
    ctx.check(f"FreeToken on the Mac: ships nothing, got {install_line(ft, 'macos')!r}",
              install_line(ft, "macos").startswith("FreeToken ships nothing for macos"))
    ctx.check("Strata: install.ps1 on Windows, install.sh on Linux and the Mac", "install.ps1" in install_line(st, "windows")
              and "install.sh" in install_line(st, "linux") and install_line(st, "macos") == install_line(st, "linux"))
    ctx.check("TensorFold: Homebrew on the Mac, the archive on Linux (no fetch), the build on Windows",
              install_line(tf, "macos").startswith("brew install") and "release archive" in install_line(tf, "linux")
              and "from source" in install_line(tf, "windows"))


@test
def test_the_table_is_the_only_place_an_engine_lives(ctx: Ctx):
    words = ("API server is ready", "owned_by\": \"FreeToken", "\"service\": \"strata\"", "streams at once",
             "1919", "Niko1221", "FlashML-org", "ashhart")
    hits = []
    for p in PKG.rglob("*.py"):
        if p.parent.name == "engines":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits += [f"{p.relative_to(PKG).as_posix()}: {w}" for w in words if w in text]
    ctx.check(f"no engine port, word or line outside engines/, got {hits}", not hits)
    old = [p.relative_to(PKG).as_posix() for p in PKG.rglob("*.py") if re.search(r"freetoken|strata|tensorfold", p.name)]
    ctx.check(f"no engine-named module left, got {old}", not old and not (PKG / "freetoken").exists())


@test
def test_the_models_rows(ctx: Ctx):
    from halo_harness.engines.descriptors import TABLE
    from halo_harness.engines.models import ROWS, match, rows
    ctx.check("every row names an engine of the table", all(r["engine"] in TABLE for r in ROWS))
    ctx.check(f"the old catalogs' counts, got {[len(rows(e)) for e in TABLE]}",
              [len(rows(e)) for e in TABLE] == [16, 24, 24])
    gpt = match("freetoken", "openai/gpt-oss-120b")
    ctx.check(f"FreeToken's sizes from the parameter counts, got {gpt}", gpt and round(gpt["size_gb"], 1) == 57.9
              and round(gpt["gpu_gb"], 2) == 2.52 and round(gpt["ram_gb"], 1) == 55.4)
    ctx.check("a served id names its Strata set", match("strata", "qwen3.8-flash-next-iq3_xxs")["id"] == "qwen/IQ3_XXS"
              and match("strata", "strata:deepseek41/ist-das-2.00bpw")["min_vram_gb"] == 12.0)
    ctx.check("a lane's model names its TensorFold row", match("tensorfold", "hf:local/Qwen3.8-27B-MLX-4bit@mac")["id"]
              == "TensorFold/Qwen3.8-27B-MLX-4bit")
    ctx.check("a pinned pull is kept", match("tensorfold", "nvidia/Qwen3.6-35B-A3B-NVFP4")["pull"].endswith(
        "@1355db6a052410cfd62085d94b58866fd0f2c3c5"))
    ctx.check("a model no engine names", match("freetoken", "qwen3.8:27b") is None and match("strata", "") is None)


@test
def test_the_docs_page_renders_the_table(ctx: Ctx):
    from halo_harness.engines.descriptors import TABLE
    page = (PKG.parent / "docs" / "MODELS-engines.md").read_text(encoding="utf-8")
    for d in TABLE.values():
        missing = [w for w in (f"`{d['id']}`", d["label"], d["url"], str(d["default_port"]), d["fit"]["rule"])
                   + tuple(v.split(" (")[0] for v in d["install"].values() if v.startswith(("uv ", "brew ", "curl ")))
                   if w not in page]
        ctx.check(f"{d['id']}: the page names its id, label, url, port, fit rule and install lines; missing {missing}",
                  not missing)
    ctx.check("the page says verified: false plainly and how to add an engine", "`verified: false`" in page
              and "## Adding an engine" in page)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
