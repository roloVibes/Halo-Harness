"""tests.test_local_hf_cli -- Halo 3.3.5.0 R5: `halo local download | ls | rm | serve | stop | servers | log` against the
fakes (tests/helpers/hf_local_env.HfHome: the fake hub on 127.0.0.1:0, the fake llama-server, box's card from the
seam; stdin is not a terminal), through local_cli.cmd_local:

1. download: the licence line and the files first; without a terminal and --yes it prints the --yes line; --yes
   downloads and prints the serve line; a gated repo without HF_TOKEN says so;
2. ls: the folder, the model's kind, size and fit word, --json;
3. serve: each flag with its source, the command line, the URL and the hf:local ref; servers; log; stop by port;
4. rm: the uses card and the --force line without a terminal; --force deletes;
5. bare `halo local` on a terminal opens the Hugging Face page (the door's page word).
Run: python -m tests.test_local_hf_cli
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import GATED, GGUF, HfHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def run(argv: list) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    buf = io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO("")
    try:
        with contextlib.redirect_stdout(buf):
            rc = cmd_local(argv)
    finally:
        sys.stdin = saved
    return rc, buf.getvalue()


@test
def test_download_licence_first_then_the_bytes(ctx: Ctx):
    with HfHome() as h:
        rc, out = run(["download", GGUF, "Tiny-1B-Q8_0.gguf"])
        ctx.check(f"no terminal: the licence, the files, the --yes line, got {rc} {out!r}", rc == 1 and "licence apache-2.0" in out
                  and "Tiny-1B-Q8_0.gguf" in out and f"halo local download {GGUF} Tiny-1B-Q8_0.gguf --dir {h.models} --yes" in out
                  and h.hub.resolves() == [])
        rc, out = run(["download", GGUF, "Tiny-1B-Q8_0.gguf", "--yes"])
        ctx.check(f"--yes downloads, the serve line, got {rc} {out[-300:]!r}", rc == 0 and "is on disk in" in out and "halo local serve " in out)
        rc, out = run(["download", GATED, "--yes"])
        ctx.check(f"gated without HF_TOKEN says so, got {rc} {out!r}", rc == 1 and "gated" in out and "HF_TOKEN" in out)


@test
def test_ls_lists_kind_size_and_fit(ctx: Ctx):
    with HfHome() as h:
        rc, out = run(["ls"])
        ctx.check(f"an empty folder says how to fill it, got {out!r}", rc == 0 and "halo local download <repo>" in out)
        run(["download", GGUF, "--yes"])
        rc, out = run(["ls"])
        line = next((ln for ln in out.splitlines() if "Tiny-1B-Q4_K_M.gguf" in ln), "")
        ctx.check(f"the model line: kind, size, fit word, got {out!r}", rc == 0 and "fit at 32,768 on box" in out
                  and line.split()[0] == "gguf" and ("fits" in line or "tight" in line))
        rc, js = run(["ls", "--json"])
        ctx.check("--json is the listing", rc == 0 and json.loads(js)["dirs"][0]["models"][0]["repo"] == GGUF)


@test
def test_serve_servers_log_stop(ctx: Ctx):
    with HfHome() as h:
        run(["download", GGUF, "--yes"])
        path = json.loads(run(["ls", "--json"])[1])["dirs"][0]["models"][0]["path"]
        rc, out = run(["serve", path])
        ctx.check(f"each flag with its source, got {out!r}", rc == 0 and "-c " in out and "the fit planner on box's card" in out
                  and "-ngl" in out and "every layer" in out and "one slot" in out)
        ctx.check(f"the command line, the URL and the ref, got {out!r}", "--host 127.0.0.1" in out and "http://127.0.0.1:" in out
                  and "use it as hf:local/Tiny-1B-Q4_K_M" in out and "it stops when the last Halo process" in out)
        rc, out = run(["servers"])
        sid = out.split()[0] if out.strip() else ""
        ctx.check(f"servers lists it ready, got {out!r}", rc == 0 and sid.startswith("llama-") and "ready" in out)
        rc, out = run(["log", sid, "-n", "5"])
        ctx.check(f"log: the tail, got {out!r}", rc == 0 and out.count("\n") <= 6 and f"{sid}.log" in out)
        rc, out = run(["stop", sid.split("-", 1)[1]])
        ctx.check(f"stop by port, got {out!r}", rc == 0 and f"stopped llama-server {sid}" in out)
        rc, out = run(["stop", "nobody"])
        ctx.check(f"a server Halo did not start, got {out!r}", rc == 1 and "did not start" in out)


@test
def test_rm_the_uses_card_then_force(ctx: Ctx):
    with HfHome() as h:
        run(["download", GGUF, "--yes"])
        path = json.loads(run(["ls", "--json"])[1])["dirs"][0]["models"][0]["path"]
        cfg = h.config()
        cfg["model"] = "hf:local/Tiny-1B-Q4_K_M"
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        rc, out = run(["rm", path])
        ctx.check(f"the uses card and the --force line, got {rc} {out!r}", rc == 1 and "the default model (`model`)" in out
                  and f"halo local rm {path} --force" in out and Path(path).exists())
        rc, out = run(["rm", path, "--force"])
        ctx.check(f"--force deletes it, got {rc} {out!r}", rc == 0 and "deleted" in out and not Path(path).exists())


@test
def test_bare_halo_local_opens_the_hugging_face_page(ctx: Ctx):
    with HfHome():
        from halo_harness import local_tab_cli as T
        seen = []
        saved = (T._open, sys.stdin, sys.stdout)

        class Tty(io.StringIO):
            def isatty(self):
                return True
        try:
            T._open = lambda page: seen.append(page) or True
            sys.stdin, sys.stdout = Tty(), Tty()
            rc = T.cmd_tab([])
        finally:
            T._open, sys.stdin, sys.stdout = saved
        ctx.check(f"the door opens huggingface, got {rc} {seen}", rc == 0 and seen == ["huggingface"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
