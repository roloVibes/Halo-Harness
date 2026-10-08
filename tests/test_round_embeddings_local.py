"""tests.test_round_embeddings_local -- Halo 2.0.7 (the old 2.0.6 scope):
local embeddings + /recall + the generic `local:` route.

  * the embeddings client: disabled until configured; Ollama /api/embed
    and OpenAI-compat /v1/embeddings transports (against a real local
    HTTP server); cosine sanity;
  * the index: incremental (mtime-keyed skip, prune of vanished
    sources), memory topics + session logs as sources;
  * search/ranking: the query's nearest topics win, ties break
    deterministically; disabled -> [] without touching the network;
  * `halo recall` CLI exit codes;
  * the `local:` route: ref parsing (default + named server), creds
    resolution (named/default/missing), per-server context discovery,
    and a REAL session turn through a local.server pointed at the mock
    upstream.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


def _text_step(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def _set_config(home: Path, key: str, value) -> None:
    """Write config.json the way get_config_value READS it: a dotted key
    is a NESTED path ("local.servers" -> {"local": {"servers": ...}})."""
    cfg_path = home / ".halo" / "config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    parts = key.split(".")
    cursor = cfg
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")


def _set_user_settings(home: Path, key: str, value) -> None:
    """User-layer ~/.claude/settings.json (the settings chain resolve_settings
    reads; autoMemoryDirectory rides here)."""
    sp = home / ".claude" / "settings.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if sp.exists():
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[key] = value
    sp.write_text(json.dumps(data), encoding="utf-8")


class _FakeEmbedder:
    """A real local HTTP server speaking Ollama's /api/embed shape, with a
    deterministic embedding function: bag-of-words over a fixed vocab --
    similar texts land near each other, dissimilar ones far apart."""

    def __init__(self):
        self.calls = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path.endswith("/v1/embeddings"):
                    outer.calls += 1
                    data = [{"embedding": _embed(t)} for t in body.get("input") or []]
                    payload = {"data": data}
                else:  # /api/embed
                    outer.calls += 1
                    payload = {"embeddings": [_embed(t) for t in body.get("input") or []]}
                blob = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


_VOCAB = ["drum", "kali", "python", "halo", "theme", "signal", "bash", "model",
          "tomatoes", "garden", "basil"]


def _embed(text: str) -> list:
    t = text.lower()
    return [1.0 if w in t else 0.0 for w in _VOCAB]


# ---- the embeddings client --------------------------------------------------------


@test
def test_embeddings_disabled_until_configured(ctx: Ctx):
    from halo_harness.providers.embeddings import embed_texts, embeddings_enabled

    home = Path(tempfile.mkdtemp(prefix="emb-off-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    ctx.check("disabled with no config", not embeddings_enabled())
    ctx.check("embed_texts returns None (never raises, never networks)",
              embed_texts(["hello"]) is None)


@test
def test_embeddings_ollama_and_openai_compat_transports(ctx: Ctx):
    from halo_harness.providers.embeddings import cosine, embed_texts, embeddings_enabled

    fake = _FakeEmbedder()
    home = Path(tempfile.mkdtemp(prefix="emb-ollama-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        _set_config(home, "embeddings", {"model": "nomic-embed-text",
                                         "base_url": fake.url})
        ctx.check("enabled once model is set", embeddings_enabled())
        vecs = embed_texts(["drum recording on kali", "completely unrelated gardening note"])
        ctx.check("two vectors came back", vecs is not None and len(vecs) == 2)
        ctx.check("the drum/kali text embeds with those dims set",
                  vecs[0][0] == 1.0 and vecs[0][1] == 1.0 and vecs[0][3] == 0.0)
        ctx.check("the gardening note is far from it",
                  cosine(vecs[0], vecs[1]) == 0.0)
        same = embed_texts(["another drum note about kali"])
        ctx.check("similar text lands near the first",
                  cosine(vecs[0], same[0]) > 0.5)
        calls_before = fake.calls
        _set_config(home, "embeddings", {"model": "x", "base_url": "http://127.0.0.1:1"})
        ctx.check("a dead transport returns None, never raises", embed_texts(["x"]) is None)
        ctx.check("the healthy server saw no new call (the dead one is a different URL)",
                  fake.calls == calls_before)
    finally:
        fake.stop()


# ---- the index + search -------------------------------------------------------------


def _seed_memory(home: Path) -> Path:
    """Seeds a memory dir and points the settings chain at it via the
    user-layer autoMemoryDirectory (the REAL path recall._memory_sources
    -> MemoryStore -> memory_dir walks)."""
    mem = home / "memory-topics"
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "drums.md").write_text("# Drums\nPractice-pad routine and double-kick exercises",
                                  encoding="utf-8")
    (mem / "gardening.md").write_text("# Gardening\nTomatoes and basil care notes",
                                       encoding="utf-8")
    _set_user_settings(home, "autoMemoryDirectory", str(mem))
    return mem


def _seed_session(state: Path, slug: str, prompt: str) -> None:
    d = state / "sessions" / slug
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"type": "meta", "title": f"session about {slug}"}),
        json.dumps({"type": "user", "content": [{"type": "text", "text": prompt}]}),
        json.dumps({"type": "assistant", "content": [{"type": "text", "text": "done"}]}),
    ]
    (d / f"{slug}.jsonl").write_text("\n".join(lines), encoding="utf-8")


@test
def test_index_build_search_and_incremental_skip(ctx: Ctx):
    fake = _FakeEmbedder()
    home = Path(tempfile.mkdtemp(prefix="emb-idx-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        _set_config(home, "embeddings", {"model": "nomic-embed-text", "base_url": fake.url})
        mem = _seed_memory(home)
        _seed_session(home, "s1", "fix the bash tool on kali")
        _seed_session(home, "s2", "plant tomatoes in the garden")

        from halo_harness import recall
        report = recall.build_index(home)
        ctx.check(f"index built over 4 sources, got {report}", report["total"] == 4)
        ctx.check("all four were embedded", report["embedded"] == 4)

        calls_after_build = fake.calls
        report2 = recall.build_index(home)
        ctx.check("nothing re-embedded on an unchanged tree", report2["embedded"] == 0)
        ctx.check("and no embed call was made at all", fake.calls == calls_after_build)

        hits = recall.search("drum recording setup", state_dir=home)
        ctx.check("search returns ranked hits", len(hits) >= 1)
        ctx.check("the drums memory topic is the top hit",
                  hits[0]["kind"] == "memory" and "drums" in hits[0]["id"].lower())
        hits2 = recall.search("tomatoes garden", state_dir=home, refresh=False)
        ctx.check("the gardening session/memory outranks drums there",
                  "drums" not in hits2[0]["id"].lower())

        (mem / "gardening.md").unlink()
        report3 = recall.build_index(home)
        ctx.check("a vanished source is pruned", report3["pruned"] == 1 and report3["total"] == 3)
    finally:
        fake.stop()


@test
def test_search_disabled_returns_empty_and_cli_exit_codes(ctx: Ctx):
    home = Path(tempfile.mkdtemp(prefix="emb-off2-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    from halo_harness import recall
    ctx.check("search on a disabled config is []", recall.search("anything", state_dir=home) == [])
    ctx.check("unconfigured CLI exits 2 with guidance",
              recall.cmd_recall(["anything"]) == 2)
    ctx.check("no query exits 2", recall.cmd_recall([]) == 2)

    fake = _FakeEmbedder()
    try:
        _set_config(home, "embeddings", {"model": "m", "base_url": fake.url})
        _seed_memory(home)
        recall.build_index(home, cwd=Path.cwd())  # ensure the topics are in
        code = recall.cmd_recall(["--build-only"])
        ctx.check(f"build-only exits 0, got {code}", code == 0)
        code2 = recall.cmd_recall(["drums"])
        ctx.check(f"a matching query exits 0, got {code2}", code2 == 0)
        code3 = recall.cmd_recall(["zzz-unmatchable-query-xyz"])
        ctx.check(f"no matches exits 1, got {code3}", code3 == 1)
    finally:
        fake.stop()


# ---- the generic local: route ---------------------------------------------------------


@test
def test_local_ref_parsing_creds_and_context(ctx: Ctx):
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import ModelProfile, parse_model_ref, resolve_model_profile

    home = Path(tempfile.mkdtemp(prefix="local-route-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    _set_config(home, "local.servers", {
        "studio": {"base_url": "http://127.0.0.1:1234/v1", "api_key": "sk-local", "context": 8192},
        "vllm": {"base_url": "http://198.51.100.5:8000/v1"},
    })

    ref = parse_model_ref("local:qwen3-30b")
    ctx.check("default-server ref parses", ref.provider == "local" and ref.model == "qwen3-30b"
              and ref.host is None and ref.dialect == "openai-chat")
    creds = _resolve_creds(ref)
    ctx.check("creds fall to the FIRST server entry",
              creds is not None and creds.base_url == "http://127.0.0.1:1234/v1"
              and creds.api_key == "sk-local")
    profile = resolve_model_profile(ref, home, {})
    ctx.check(f"per-server context discovered, got {profile.context_tokens}",
              profile.context_tokens == 8192)

    ref2 = parse_model_ref("local:my-model@vllm")
    ctx.check("named-server ref parses", ref2.provider == "local" and ref2.host == "vllm")
    creds2 = _resolve_creds(ref2)
    ctx.check("named creds resolve", creds2 is not None and creds2.base_url == "http://198.51.100.5:8000/v1")
    profile2 = resolve_model_profile(ref2, home, {})
    ctx.check("no context declared -> the default 128k", profile2.context_tokens == 128000)

    ref3 = parse_model_ref("local:x@nosuch")
    ctx.check("a missing NAMED entry has no creds (an error, never a silent default)",
              _resolve_creds(ref3) is None)
    try:
        parse_model_ref("local:")
        ctx.check("bare local: refused", False)
    except Exception:
        ctx.check("bare local: refused with InvalidModelError", True)


@test
def test_local_route_real_turn_through_the_mock(ctx: Ctx):
    # The mock dispatches scenarios by the WIRE model name -- a local: ref
    # sends the bare id, so register under "test-model".
    SCENARIOS["local-lane"] = ScriptedTurns([_text_step("local lane answers")])
    mock = MockUpstream().start()
    try:
        from halo_harness.agent.assemble import SessionContext
        from halo_harness.agent.loop import Session
        from halo_harness.model import parse_model_ref, resolve_model_profile
        from halo_harness.permissions import PermissionEngine
        from halo_harness.providers.stream import ProviderCreds

        home = Path(tempfile.mkdtemp(prefix="local-e2e-"))
        os.environ["BRIDGE_TEST_HOME"] = str(home)
        _set_config(home, "local.servers",
                    {"mock": {"base_url": mock.base_url, "context": 32768}})
        cwd = Path(tempfile.mkdtemp(prefix="local-e2e-cwd-"))
        ref = parse_model_ref("local:mock/local-lane@mock")
        session = Session(
            cwd=cwd, model_ref=ref, model_profile=resolve_model_profile(ref, home, {}),
            creds=ProviderCreds(base_url=mock.base_url, api_key=""),
            state_dir=home / ".halo" if (home / ".halo").exists() else home,
            model_label=ref.raw,
            session_context=SessionContext(cwd=cwd, model_label=ref.raw, bare=True),
            openrouter_base_url=None, max_turns=4,
            permission_engine=PermissionEngine(mode="auto", cwd=cwd),
            agents={}, routes={},
        )
        evs = list(session.turn("say something"))
        texts = [e.data.get("text", "") for e in evs if e.kind == "text_delta"]
        ctx.check("the turn completed on the local lane",
                  any("local lane answers" in t for t in texts))
        ctx.check("the request really hit the mock server", len(mock.requests) >= 1)
        if mock.requests:
            ctx.check("the wire model id is the bare name",
                      (mock.requests[0].get("body") or {}).get("model") == "mock/local-lane")
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
