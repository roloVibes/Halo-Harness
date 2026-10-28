"""tests.test_models_control_cli -- Halo 3.3.5.0 R3: `halo models pull | rm | show --host | load | unload | copy |
rename | twin | loaded` (halo_harness/models_control_cli.py, model_card_cli.py) in-process against the fake Ollama
`box` on 127.0.0.1:0 (tests/helpers/control_env.Box): each subcommand's line and exit code, `--json`, rm's uses card
(a role names the model: it asks, and without a terminal it says the --force line; --force deletes; a live session
on it keeps it), show's /api/show lines under the card, the progress line a pull prints. Never a real server.
Run: python -m tests.test_models_control_cli
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.control_env import Box  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def halo(*argv) -> "tuple[int, str, str]":
    from halo_harness.catalog_cli import cmd_models
    out, err = io.StringIO(), io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO("")  # no terminal: rm never waits on input
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = cmd_models(list(argv))
            except SystemExit as e:
                rc = e.code
    finally:
        sys.stdin = saved
    return rc, out.getvalue(), err.getvalue()


def _tags(b) -> list:
    return [t["model"] for t in b.mock.tags_response["models"]]


@test
def test_pull_and_its_progress_line(ctx: Ctx):
    from halo_harness.models_control_cli import progress_line
    with Box() as b:
        rc, out, err = halo("pull", "qwen3.5:9b", "--host", "box")
        ctx.check(f"rc 0, the success line, got {rc} {out!r} {err!r}", rc == 0 and "qwen3.5:9b pulled on box" in out
                  and "qwen3.5:9b" in _tags(b))
        rc, out, err = halo("pull", "nope:1b", "--json")
        got = json.loads(out)
        ctx.check(f"a name it cannot pull: rc 1, the error in the JSON, got {rc} {got}", rc == 1 and "file does not exist" in got["say"])
        line = progress_line({"status": "pulling 1a2b3c", "percent": 45.0, "completed": 1.2e9, "total": 2.7e9,
                              "speed": 1.2e8, "eta": 13})
        ctx.check(f"the progress line, got {line!r}", line == "pulling 1a2b3c  45.0 %  1.2 GB of 2.7 GB  120 MB/s  eta 13 s")
        rc, _o, err = halo("pull", "x", "--host", "nowhere")
        ctx.check(f"an unknown host: rc 1, said, got {rc} {err!r}", rc == 1 and "no Ollama host named 'nowhere'" in err)


@test
def test_rm_prints_the_uses_card_and_asks(ctx: Ctx):
    from halo_harness.studio import local_uses
    with Box() as b:
        cfg = json.loads((b.state / "config.json").read_text(encoding="utf-8"))
        cfg["roles"] = {"reviewer": "ol:qwen3:30b@box"}
        (b.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        rc, out, err = halo("rm", "qwen3:30b")
        ctx.check(f"the uses card, then the --force line, kept, got {rc} {out!r} {err!r}", rc == 1 and "`reviewer` role" in out
                  and "halo models rm qwen3:30b --force" in err and "qwen3:30b" in _tags(b))
        local_uses.READERS["live"] = lambda: [{"session_id": "s1", "title": "t", "model": "ol:qwen3:30b@box"}]
        try:
            rc, out, err = halo("rm", "qwen3:30b", "--force")
            ctx.check(f"a live session on it: rc 1, kept, got {rc} {err!r}", rc == 1 and "1 live session(s)" in err and "qwen3:30b" in _tags(b))
        finally:
            local_uses.READERS.clear()
        rc, out, _e = halo("rm", "qwen3:30b", "--force")
        ctx.check(f"--force deletes it, got {rc} {out!r}", rc == 0 and "qwen3:30b deleted from box" in out and "qwen3:30b" not in _tags(b))
        rc, _o, err = halo("rm", "gpt-oss:20b")
        ctx.check(f"nothing uses it: deleted at once, got {rc}", rc == 0 and "gpt-oss:20b" not in _tags(b))
        rc, _o, err = halo("rm", "gpt-oss:20b")
        ctx.check(f"gone already: rc 1, HTTP 404, got {rc} {err!r}", rc == 1 and "HTTP 404" in err)


@test
def test_show_with_host_prints_the_api_show_lines(ctx: Ctx):
    with Box() as b:
        halo("pull", "qwen3.5:9b")
        rc, out, _e = halo("show", "qwen3.5:9b", "--host", "box")
        ctx.check(f"the card, then /api/show's facts, got {rc} {out[-600:]!r}", rc == 0 and "/api/show: family qwen35" in out
                  and "parameters: temperature 0.7" in out and "licence: Apache License 2.0" in out)
        rc, out, _e = halo("show", "qwen3.5:9b", "--host", "box", "--json")
        got = json.loads(out)
        ctx.check(f"--json carries api_show, got {sorted(got)}", rc == 0 and got["api_show"]["facts"]["context"] == 262144)


@test
def test_load_unload_copy_rename_twin_loaded(ctx: Ctx):
    with Box() as b:
        rc, out, _e = halo("load", "qwen3:30b", "--num-ctx", "8192", "--keep-alive", "-1")
        ctx.check(f"loaded, the window and keep-alive on the wire, got {rc} {out!r} {b.mock.generated}", rc == 0
                  and b.mock.generated[-1]["options"] == {"num_ctx": 8192} and b.mock.generated[-1]["keep_alive"] == -1)
        rc, out, _e = halo("loaded")
        ctx.check(f"loaded lists it, got {rc} {out!r}", rc == 0 and out.startswith("qwen3:30b  100% on the GPU  window 8192"))
        rc, out, _e = halo("unload", "qwen3:30b")
        ctx.check(f"unloaded, got {rc} {out!r}", rc == 0 and b.mock.generated[-1]["keep_alive"] == 0)
        rc, out, _e = halo("copy", "qwen3:30b", "qwen3-mine:30b")
        ctx.check(f"copied, got {rc} {out!r}", rc == 0 and "qwen3-mine:30b" in _tags(b))
        rc, out, _e = halo("rename", "qwen3-mine:30b", "qwen3-b:30b")
        ctx.check(f"renamed, got {rc} {out!r}", rc == 0 and "qwen3-b:30b" in _tags(b) and "qwen3-mine:30b" not in _tags(b))
        rc, out, _e = halo("twin", "qwen3:30b", "--window", "16384")
        ctx.check(f"the twin: its plan line, progress, the ref, got {rc} {out!r}", rc == 0 and "qwen3-halo:30b on 'box': FROM qwen3:30b"
                  in out and "[ol:qwen3-halo:30b@box]" in out and "qwen3-halo:30b" in _tags(b))
        rc, _o, err = halo("twin", "qwen3:30b")
        ctx.check(f"twin needs --window, got {rc}", rc == 2)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
