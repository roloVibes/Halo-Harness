"""tests.test_voice_install -- Halo 3.3.9.0 R1: a speech model on disk (halo_harness/voice/install.py, `halo voice
download | rm`), through the fake hub of tests/helpers/hf_local_env.HfHome (a scratch home, one model folder,
HF_ENDPOINT on 127.0.0.1:0, two speech repos whose README the download leaves out):

1. present() is None, then `halo voice download <model> --yes` says the size, the repo and the folder first, fetches
   only the files the engine loads into the hub layout, and present() finds the snapshot; again: "is present";
2. without a terminal and without --yes it prints the line to run and fetches nothing;
3. a repo that does not list the engine's files says so (the repo id is from memory) and fetches nothing;
4. HF_TOKEN goes to the hub only: no file under the home holds it;
5. `halo voice rm` refuses while a speech server serves the model, then deletes the repo folder;
6. a plain folder named after the repo counts as present.
Run: python -m tests.test_voice_install
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import HfHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SMALL = "faster-whisper:small.en"


def _voice(*argv) -> "tuple[int, str]":
    from halo_harness.voice_cli import cmd_voice
    out = io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO("")  # no terminal to ask on
    try:
        with contextlib.redirect_stdout(out):
            code = cmd_voice(list(argv))
    finally:
        sys.stdin = saved
    return code, out.getvalue()


@test
def test_download_says_the_size_first_and_fetches_the_engines_files(ctx: Ctx):
    from halo_harness.voice.install import present
    with HfHome() as h:
        ctx.check("absent at first", present(SMALL) is None)
        code, out = _voice("download", SMALL, "--yes")
        first = out.splitlines()[0] if out else ""
        ctx.check(f"the size, the repo and the folder first, got {first!r}", first == (
            f"{SMALL}: 0.5 GB from Systran/faster-whisper-small.en (repo unverified) into {h.models}"))
        ctx.check(f"downloaded, got {code}: {out!r}", code == 0 and f"{SMALL} is on disk in " in out
                  and f"serve it: halo local serve --stt {SMALL}" in out)
        where = present(SMALL)
        ctx.check(f"present in the hub layout, got {where}", where is not None and where.parent.name == "snapshots"
                  and where.parent.parent.name == "models--Systran--faster-whisper-small.en")
        names = sorted(p.name for p in where.iterdir())
        ctx.check(f"only the engine's files, got {names}", names == sorted(["config.json", "model.bin", "tokenizer.json",
                                                                           "vocabulary.txt"]))
        code, out = _voice("download", SMALL)
        ctx.check(f"again: present, got {out!r}", code == 0 and out.startswith(f"{SMALL} is present: "))


@test
def test_no_terminal_no_yes_fetches_nothing(ctx: Ctx):
    from halo_harness.voice.install import present
    with HfHome() as h:
        code, out = _voice("download", "kokoro-82m")
        ctx.check(f"the line to run, got {code} {out!r}", code == 1 and "halo voice download kokoro-82m --yes" in out)
        ctx.check("nothing on disk", present("kokoro-82m") is None and not any(h.models.iterdir()))


@test
def test_a_repo_without_the_engines_files_says_so(ctx: Ctx):
    with HfHome() as h:
        h.hub.add("Systran/faster-whisper-base.en", {"README.md": b"# moved\n"}, kind="voice")
        code, out = _voice("download", "faster-whisper:base.en", "--yes")
        ctx.check(f"the files it lacks, from memory, got {code} {out!r}", code == 1 and "does not list config.json"
                  in out and "unverified" in out)
        ctx.check("nothing on disk", not any(h.models.iterdir()))


@test
def test_the_token_goes_to_the_hub_only(ctx: Ctx):
    from tests.helpers.hf_local_env import TOKEN
    with HfHome() as h:
        os.environ["HF_TOKEN"] = TOKEN
        code, _out = _voice("download", "kokoro-82m", "--yes")
        ctx.check(f"downloaded, got {code}", code == 0)
        leaked = [str(p) for p in Path(h.root).rglob("*") if p.is_file()
                  and TOKEN.encode() in p.read_bytes()]
        ctx.check(f"no file holds the token, got {leaked}", not leaked)


@test
def test_rm_refuses_while_served_then_deletes(ctx: Ctx):
    import json
    from halo_harness.voice.install import present
    from tests.helpers.voice_files import put
    with HfHome() as h:
        put(h.models, SMALL)
        reg = h.state / "run" / "local-servers.json"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(json.dumps([{"id": "stt", "kind": "voice-stt", "model": SMALL, "port": 9, "pid": os.getpid(),
                                    "halo": True}]), encoding="utf-8")
        code, out = _voice("rm", SMALL, "--force")
        ctx.check(f"refused while stt serves it, got {code} {out!r}", code == 1 and "halo local stop stt first" in out)
        reg.write_text("[]", encoding="utf-8")
        code, out = _voice("rm", SMALL, "--force")
        ctx.check(f"deleted, got {code} {out!r}", code == 0 and out.startswith("  ") and "deleted " in out
                  and "models--Systran--faster-whisper-small.en" in out)
        ctx.check("gone", present(SMALL) is None and not (h.models / "models--Systran--faster-whisper-small.en").exists())
        code, out = _voice("rm", SMALL)
        ctx.check("not on disk now", code == 1 and "is not on disk" in out)


@test
def test_a_plain_folder_counts(ctx: Ctx):
    from halo_harness.voice.catalog import get
    from halo_harness.voice.install import present
    with HfHome() as h:
        d = h.models / "kokoro-onnx"
        d.mkdir()
        for f in get("kokoro-82m").files:
            (d / f).write_bytes(b"x")
        ctx.check(f"present: the folder named after the repo, got {present('kokoro-82m')}", present("kokoro-82m") == d)
        (d / "voices-v1.0.bin").unlink()
        ctx.check("one file missing: not present", present("kokoro-82m") is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
