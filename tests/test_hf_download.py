"""tests.test_hf_download -- Halo 3.3.5.0 R5: providers/hf_download.py against the fake hub (tests/helpers/mock_hub.py
on 127.0.0.1:0, named by HF_ENDPOINT; BRIDGE_TEST_NO_BACKGROUND_NET=1, a fresh BRIDGE_TEST_HOME):

1. one GGUF file lands in the hub cache layout (snapshots/<commit>/<file>, refs/main), checked against the LFS sha256,
   with the pull job's {digest, total, completed} frames;
2. a whole MLX repo (every file but .gitattributes), the folder the model-dir scan then finds;
3. a GGUF repo's default quant (Q4_K_M before Q8_0, its shards together) and a quant word picking a group;
4. resume from a .part (Range: bytes=N-, a 206), and a server that ignores Range (a 200 starts it again);
5. a sha256 mismatch: the error says so, the part is removed, nothing lands;
6. a gated repo: the licence line before any byte, no token -> the line and no request for a file, a wrong token ->
   the hub's 401 as one line, the right token -> the file;
7. a cancel keeps the part; the next download resumes from it; under the test flag the real hub is never read.
Run: python -m tests.test_hf_download
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_hub import COMMIT, MockHub, gguf_bytes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "HF_ENDPOINT", "HF_TOKEN")
REPO = "example-org/Tiny-1B-GGUF"


class Hub:
    def __init__(self, endpoint: bool = True):
        self.endpoint = endpoint

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="l4_dl-")).resolve()
        for k in ("BRIDGE_STATE_DIR", "HF_TOKEN", "HF_ENDPOINT"):
            os.environ.pop(k, None)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_TEST_NO_BACKGROUND_NET="1")
        self.hub = MockHub().start()
        if self.endpoint:
            os.environ["HF_ENDPOINT"] = self.hub.base_url
        self.dest = self.root / "models"
        self.dest.mkdir()
        self.q4, self.q8 = gguf_bytes(300_000, "q4"), gguf_bytes(500_000, "q8")
        self.hub.add(REPO, {".gitattributes": b"*.gguf filter=lfs\n", "README.md": b"# Tiny\n",
                            "Tiny-1B-Q4_K_M.gguf": self.q4, "Tiny-1B-Q8_0.gguf": self.q8,
                            "BF16/Tiny-1B-BF16-00001-of-00002.gguf": gguf_bytes(200_000, "a"),
                            "BF16/Tiny-1B-BF16-00002-of-00002.gguf": gguf_bytes(100_000, "b")})
        return self

    def __exit__(self, *exc):
        self.hub.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _dl(h, repo=REPO, file=None, **kw):
    from halo_harness.providers.hf_download import download
    frames: list = []
    got = download(repo, file, dest_dir=h.dest, on_status=frames.append, **kw)
    return got, frames


@test
def test_one_gguf_file_into_the_hub_cache_layout(ctx: Ctx):
    with Hub() as h:
        got, frames = _dl(h, file="Tiny-1B-Q4_K_M.gguf")
        snap = h.dest / f"models--{REPO.replace('/', '--')}" / "snapshots" / COMMIT / "Tiny-1B-Q4_K_M.gguf"
        ctx.check(f"ok, the path in snapshots/<commit>, got {got.get('ok')} {got.get('say')} {got.get('path')}",
                  got.get("ok") and Path(got["path"]) == snap and snap.read_bytes() == h.q4)
        ctx.check(f"checked against the LFS sha256, got {got['files']}", got["files"][0]["checked"] == "sha256")
        ctx.check("refs/main is the commit", (snap.parents[2] / "refs" / "main").read_text() == COMMIT)
        last = frames[-1]
        ctx.check(f"frames have the pull job's shape, got {last}", last["digest"] == "Tiny-1B-Q4_K_M.gguf"
                  and last["total"] == len(h.q4) and last["completed"] == len(h.q4))
        ctx.check("no part file left", not list((snap.parents[2] / "blobs").glob("*.part")))
        again, _f = _dl(h, file="Tiny-1B-Q4_K_M.gguf")
        ctx.check(f"a second ask finds it on disk, got {again['files']}", again["ok"] and again["files"][0].get("skipped"))


@test
def test_a_whole_mlx_repo_and_the_scan_finds_it(ctx: Ctx):
    with Hub() as h:
        files = {".gitattributes": b"x\n", "config.json": b'{"model_type": "qwen2", "num_hidden_layers": 4}',
                 "model.safetensors": b"\0" * 70_000, "tokenizer.json": b"{}", "README.md": b"# mlx\n"}
        h.hub.add("mlx-community/Tiny-4bit", files, kind="mlx")
        got, _f = _dl(h, "mlx-community/Tiny-4bit")
        names = sorted(f["name"] for f in got.get("files") or [])
        ctx.check(f"every file but .gitattributes, got {got.get('say')} {names}",
                  got.get("ok") and names == ["README.md", "config.json", "model.safetensors", "tokenizer.json"])
        ctx.check(f"small files checked by the git blob sha1, got {got['files']}",
                  {f["name"]: f["checked"] for f in got["files"]}["config.json"] == "git blob sha1")
        from halo_harness.providers.local_model_dirs import scan_model_dirs
        found = scan_model_dirs([h.dest])
        ctx.check(f"the scan finds an mlx folder at the snapshot, got {[(str(e.path), e.format) for e in found]}",
                  [e.format for e in found] == ["mlx"] and str(found[0].path) == got["path"])


@test
def test_the_default_quant_and_a_quant_word(ctx: Ctx):
    with Hub() as h:
        from halo_harness.providers.hf_download import prepare
        plan = prepare(REPO)
        ctx.check(f"Q4_K_M by default, got {[f['name'] for f in plan['files']]}",
                  [f["name"] for f in plan["files"]] == ["Tiny-1B-Q4_K_M.gguf"] and plan["quant"] == "Q4_K_M")
        bf = prepare(REPO, "BF16")
        ctx.check(f"a quant word picks its shards, got {[f['name'] for f in bf['files']]} {bf['total']}",
                  len(bf["files"]) == 2 and bf["total"] == 300_000)
        shard = prepare(REPO, "BF16/Tiny-1B-BF16-00001-of-00002.gguf")
        ctx.check("one shard's name brings the other", len(shard["files"]) == 2)
        from halo_harness.providers.hf_download import HubError
        try:
            prepare(REPO, "nope.gguf")
            ctx.check("an unknown file raises", False)
        except HubError as e:
            ctx.check(f"an unknown file lists what the repo has, got {e.message}", e.kind == "no_file" and "Q8_0" in e.message)


@test
def test_resume_from_a_part_and_a_server_that_ignores_range(ctx: Ctx):
    with Hub() as h:
        from halo_harness.providers.hf_download import prepare
        plan = prepare(REPO, "Tiny-1B-Q8_0.gguf")
        blobs = h.dest / f"models--{REPO.replace('/', '--')}" / "blobs"
        blobs.mkdir(parents=True)
        (blobs / f"{plan['files'][0]['sha256']}.part").write_bytes(h.q8[:123_456])
        got, _f = _dl(h, file="Tiny-1B-Q8_0.gguf")
        rng = [r["range"] for r in h.hub.resolves()]
        ctx.check(f"resumed with Range from the part, got {got.get('say')} {got.get('files')} {rng}",
                  got.get("ok") and got["files"][0]["resumed_from"] == 123_456 and rng == ["bytes=123456-"]
                  and Path(got["path"]).read_bytes() == h.q8)
        Path(got["path"]).unlink()
        (blobs / f"{plan['files'][0]['sha256']}.part").write_bytes(h.q8[:50_000])
        h.hub.no_range = True
        again, _f = _dl(h, file="Tiny-1B-Q8_0.gguf")
        ctx.check(f"a 200 to a Range starts the part again, got {again.get('say')} {again.get('files')}",
                  again.get("ok") and again["files"][0]["resumed_from"] == 0 and Path(again["path"]).read_bytes() == h.q8)


@test
def test_a_sha256_mismatch_is_an_error_and_lands_nothing(ctx: Ctx):
    with Hub() as h:
        h.hub.corrupt(REPO, "Tiny-1B-Q4_K_M.gguf")
        got, _f = _dl(h, file="Tiny-1B-Q4_K_M.gguf")
        root = h.dest / f"models--{REPO.replace('/', '--')}"
        ctx.check(f"the error says sha256, got {got}", not got["ok"] and got["error"] == "checksum" and "sha256" in got["say"])
        ctx.check("the part is removed and nothing is in snapshots",
                  not list((root / "blobs").glob("*.part")) and not (root / "snapshots").exists())


@test
def test_a_gated_repo_wants_the_token_and_shows_the_licence_first(ctx: Ctx):
    with Hub() as h:
        from halo_harness.providers.hf_download import prepare
        h.hub.add("example-org/Gated-2B-GGUF", {"Gated-2B-Q4_K_M.gguf": gguf_bytes(90_000, "g")}, gated="manual",
                  token="hf_fixture_token", license="gemma", prompt="Accept the fixture licence.")
        plan = prepare("example-org/Gated-2B-GGUF")
        ctx.check(f"the licence line first, got {plan['licence']}", plan["needs_token"] and "licence gemma" in plan["licence"]["line"]
                  and "gated (manual)" in plan["licence"]["line"] and plan["licence"]["prompt"].startswith("Accept"))
        got, _f = _dl(h, "example-org/Gated-2B-GGUF")
        ctx.check(f"no token: the line, no file asked for, got {got.get('say')}",
                  got["error"] == "gated" and "HF_TOKEN" in got["say"] and h.hub.resolves() == [])
        bad, _f = _dl(h, "example-org/Gated-2B-GGUF", token="hf_wrong")
        ctx.check(f"a wrong token: the hub's 401 in one line, got {bad.get('say')}", bad["error"] == "gated" and "401" in bad["say"])
        good, _f = _dl(h, "example-org/Gated-2B-GGUF", token="hf_fixture_token")
        ctx.check(f"the right token: the file, got {good.get('say')}", good.get("ok")
                  and h.hub.resolves()[-1]["auth"] == "Bearer " + "hf_fixture_token")


@test
def test_a_cancel_keeps_the_part_and_the_real_hub_is_never_read(ctx: Ctx):
    with Hub() as h:
        h.hub.add("example-org/Big-GGUF", {"Big-Q4_K_M.gguf": gguf_bytes(3 * 1024 * 1024, "big")})
        h.hub.delay_s = 0.01
        stop = threading.Event()

        def on(obj):
            if obj.get("completed"):
                stop.set()
        from halo_harness.providers.hf_download import download
        got = download("example-org/Big-GGUF", dest_dir=h.dest, on_status=on, cancel=stop)
        part = Path(got.get("part") or "")
        ctx.check(f"cancelled, the part kept, got {got.get('say')}", got.get("cancelled") and part.is_file()
                  and 0 < part.stat().st_size < 3 * 1024 * 1024 and "resumes" in got["say"])
        h.hub.delay_s = 0.0
        have = part.stat().st_size
        again = download("example-org/Big-GGUF", dest_dir=h.dest)
        ctx.check(f"the next one resumes from it, got {again.get('files')}", again.get("ok") and again["files"][0]["resumed_from"] == have)
    with Hub(endpoint=False) as h:
        from halo_harness.providers.hf_download import HubError, prepare
        try:
            prepare(REPO)
            ctx.check("the real hub is not read under the flag", False)
        except HubError as e:
            ctx.check(f"blocked under the flag, got {e.message}", e.kind == "blocked")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
