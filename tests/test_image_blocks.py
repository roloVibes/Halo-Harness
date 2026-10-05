"""tests.test_image_blocks -- Halo 2.0.3.1 (clipboard image paste):
per-dialect image conversion (Anthropic unchanged, OpenAI chat `image_url`
data URL, the Responses dialect's real `input_image`, Ollama's native
`images` field), the `cx:` `-i <path>` argv, the no-vision plain-line
fallback, the log storing a path never the base64, and resume rebuilding
the real block from that saved path.
"""
from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, _finish

test, TESTS = new_registry()

# build_cx_argv resolves the real launcher; on a machine without codex (the
# Linux suite venvs) point Halo at the fake so the argv test runs anywhere.
import os as _os
if not _os.environ.get("HALO_CODEX_EXE"):
    _os.environ["HALO_CODEX_EXE"] = '"' + sys.executable + '" "' + str(
        Path(__file__).resolve().parent / "helpers" / "fake_codex.py") + '"'


def _new_session(fh, mock, *, model="or:mock/model", vision=False):
    """Same minimal in-process construction `tests/test_loop_retries.py`
    uses -- a real `Session`, no subprocess, pointed at a `MockUpstream`
    HTTP server instead of a real provider."""
    import os
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    session_ctx = SessionContext(cwd=fh["proj"], model_label=model)
    model_ref = parse_model_ref(model)
    return Session(
        cwd=fh["proj"], model_ref=model_ref, model_profile=ModelProfile(vision=vision),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="image-blocks-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=4,
    )


def _one_shot_text_scenario(h, _body) -> None:
    _finish(h, [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": "ok"}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ])

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY"
    "42YAAAAASUVORK5CYII="
)
_TINY_PNG_B64 = base64.b64encode(_TINY_PNG).decode("ascii")

_IMAGE_BLOCK = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _TINY_PNG_B64}}


# ---------------------------------------------------------------------------
# Per-dialect conversion (pure request-builder calls, no network).
# ---------------------------------------------------------------------------

@test
def test_anthropic_dialect_keeps_the_image_block_unchanged(ctx: Ctx):
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.request import build_anthropic_request_body
    from halo_harness.providers.routing import Route
    route = Route(provider="anthropic", upstream_model="claude-sonnet-5", dialect="anthropic-passthrough")
    profile = resolve_profile(route)
    messages = [{"role": "user", "content": [{"type": "text", "text": "look"}, _IMAGE_BLOCK]}]
    body = build_anthropic_request_body(system_text="", messages=messages, route=route, profile=profile)
    user_msg = next(m for m in body["messages"] if m["role"] == "user")
    image_blocks = [b for b in user_msg["content"] if b.get("type") == "image"]
    ctx.check(f"exactly one image block, byte-identical, got {image_blocks}",
              len(image_blocks) == 1 and image_blocks[0]["source"]["data"] == _TINY_PNG_B64)


@test
def test_openai_chat_dialect_gets_an_image_url_data_url(ctx: Ctx):
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.request import build_request_body
    from halo_harness.providers.routing import Route
    route = Route(provider="openrouter", upstream_model="deepseek/deepseek-v4.1-flash", dialect="openai-chat")
    profile = resolve_profile(route)
    messages = [{"role": "user", "content": [{"type": "text", "text": "look"}, _IMAGE_BLOCK]}]
    body = build_request_body(system_text="", messages=messages, route=route, profile=profile)
    user_msg = next(m for m in body["messages"] if m["role"] == "user")
    image_parts = [p for p in user_msg["content"] if p.get("type") == "image_url"]
    ctx.check(f"exactly one image_url part with a data: URL, got {image_parts}",
              len(image_parts) == 1
              and image_parts[0]["image_url"]["url"] == f"data:image/png;base64,{_TINY_PNG_B64}")


@test
def test_responses_dialect_gets_a_real_input_image_item(ctx: Ctx):
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.responses_request import build_openai_responses_body
    from halo_harness.providers.routing import Route
    route = Route(provider="openai", upstream_model="gpt-6-astra", dialect="openai-responses")
    profile = resolve_profile(route)
    messages = [{"role": "user", "content": [{"type": "text", "text": "look"}, _IMAGE_BLOCK]}]
    body = build_openai_responses_body(system_text="", messages=messages, route=route, profile=profile)
    user_item = next(i for i in body["input"] if i.get("role") == "user")
    image_parts = [p for p in user_item["content"] if p.get("type") == "input_image"]
    ctx.check(f"exactly one real input_image part, got {image_parts}",
              len(image_parts) == 1 and image_parts[0]["image_url"] == f"data:image/png;base64,{_TINY_PNG_B64}")


@test
def test_ollama_dialect_gets_the_native_images_field(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_request import build_ollama_request_body
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    route = Route(provider="ollama", upstream_model="qwen3-vl:30b", dialect="ollama")
    profile = resolve_profile(route)
    host = OllamaHost(name="default", url="http://127.0.0.1:11434")
    messages = [{"role": "user", "content": [{"type": "text", "text": "look"}, _IMAGE_BLOCK]}]
    body = build_ollama_request_body(system_text="s", messages=messages, tools=None, tool_choice=None,
                                      route=route, profile=profile, effort=None, host=host)
    user_msg = next(m for m in body["messages"] if m["role"] == "user")
    ctx.check(f"content stays plain text, got {user_msg['content']!r}", user_msg["content"] == "look")
    ctx.check(f"images is a plain list of base64 strings, got {user_msg.get('images')}",
              user_msg.get("images") == [_TINY_PNG_B64])


@test
def test_ollama_dialect_omits_images_key_for_a_text_only_message(ctx: Ctx):
    """No regression for the common case -- an ordinary text-only message
    must never grow an empty `"images": []` key."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_request import build_ollama_request_body
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    route = Route(provider="ollama", upstream_model="qwen3:30b", dialect="ollama")
    profile = resolve_profile(route)
    host = OllamaHost(name="default", url="http://127.0.0.1:11434")
    messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    body = build_ollama_request_body(system_text="s", messages=messages, tools=None, tool_choice=None,
                                      route=route, profile=profile, effort=None, host=host)
    user_msg = next(m for m in body["messages"] if m["role"] == "user")
    ctx.check(f"no images key at all, got {user_msg}", "images" not in user_msg)


@test
def test_cx_argv_carries_dash_i_with_the_saved_path(ctx: Ctx):
    from halo_harness.agent.codex_process import build_cx_argv
    argv = build_cx_argv(model="gpt-5-codex", prompt="look at this", resume_id=None,
                          permission_mode="default", mcp_override_args=[],
                          image_paths=["/tmp/clip-1.png", "/tmp/clip-2.jpg"])
    ctx.check(f"-i for each path, got {argv}",
              "-i" in argv and argv[argv.index("-i") + 1] == "/tmp/clip-1.png"
              and argv.count("-i") == 2 and "/tmp/clip-2.jpg" in argv)


# ---------------------------------------------------------------------------
# agent.image_attach: logging strips the base64, rehydration rebuilds it.
# ---------------------------------------------------------------------------

@test
def test_image_block_for_log_carries_the_path_never_the_base64(ctx: Ctx):
    from halo_harness.agent.image_attach import image_block_for_log
    wire = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _TINY_PNG_B64},
            "image_path": "/fake/clip-1.png", "width": 1, "height": 1}
    logged = image_block_for_log(wire)
    ctx.check(f"no source/data key at all, got {logged}", "source" not in logged and "data" not in logged)
    ctx.check(f"path/media_type/dims all survive, got {logged}",
              logged == {"type": "image", "image_path": "/fake/clip-1.png",
                         "media_type": "image/png", "width": 1, "height": 1})


@test
def test_rehydrate_image_block_reads_the_file_back_into_a_real_block(ctx: Ctx):
    from halo_harness.agent.image_attach import rehydrate_image_block
    d = Path(tempfile.mkdtemp(prefix="halo-rehydrate-"))
    path = d / "clip-1.png"
    path.write_bytes(_TINY_PNG)
    logged = {"type": "image", "image_path": str(path), "media_type": "image/png", "width": 1, "height": 1}
    real = rehydrate_image_block(logged)
    ctx.check(f"a real base64 block, byte-identical to the file, got {real}",
              real["type"] == "image" and real["source"]["data"] == _TINY_PNG_B64
              and real["source"]["media_type"] == "image/png")


@test
def test_rehydrate_image_block_missing_file_degrades_to_a_text_note(ctx: Ctx):
    from halo_harness.agent.image_attach import rehydrate_image_block
    logged = {"type": "image", "image_path": "/does/not/exist/clip-9.png", "media_type": "image/png"}
    out = rehydrate_image_block(logged)
    ctx.check(f"a plain text block naming the missing path, got {out}",
              out["type"] == "text" and "/does/not/exist/clip-9.png" in out["text"])


@test
def test_rehydrate_messages_is_a_cheap_no_op_for_a_message_with_no_image(ctx: Ctx):
    from halo_harness.agent.image_attach import rehydrate_messages
    messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    out = rehydrate_messages(messages)
    ctx.check("the unchanged message is returned BY REFERENCE (the cheap fast path)", out[0] is messages[0])


# ---------------------------------------------------------------------------
# A real Session: the log stores a path never the base64, resume rebuilds
# the real block, and a no-vision model gets a plain-line path mention.
# ---------------------------------------------------------------------------

@test
def test_log_node_stores_the_path_never_the_base64_for_a_vision_model(ctx: Ctx):
    SCENARIOS["img-vision-ok"] = _one_shot_text_scenario
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _new_session(fh, mock, model="or:mock/img-vision-ok", vision=True)
        clip_path = Path(tempfile.mkdtemp(prefix="halo-clip-")) / "clip-1.png"
        clip_path.write_bytes(_TINY_PNG)
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _TINY_PNG_B64},
                 "image_path": str(clip_path), "width": 1, "height": 1}
        events_ = list(session.turn("look at this", images=[image]))
        ctx.check("the turn finished", any(e.kind == "turn_done" for e in events_))
        user_node = next(n for n in session.log.nodes() if n.get("type") == "user")
        image_block = next(b for b in user_node["content"] if isinstance(b, dict) and b.get("type") == "image")
        ctx.check(f"image_path is logged, got {image_block}", image_block.get("image_path") == str(clip_path))
        ctx.check(f"no source/data on the LOGGED node, got {image_block}",
                  "source" not in image_block and "data" not in image_block)
    finally:
        mock.stop()


@test
def test_resume_rebuilds_the_real_block_from_the_logged_path(ctx: Ctx):
    """A FRESH `SessionLog`, read back from the same file on disk (what a
    real `--resume` does) -- `derive_request` + `rehydrate_messages` must
    reconstruct the exact original image bytes from the saved path."""
    from halo_harness.agent.derive import derive_request
    from halo_harness.agent.image_attach import rehydrate_messages
    from halo_harness.agent.log import SessionLog
    SCENARIOS["img-resume"] = _one_shot_text_scenario
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _new_session(fh, mock, model="or:mock/img-resume", vision=True)
        clip_path = Path(tempfile.mkdtemp(prefix="halo-clip-")) / "clip-1.png"
        clip_path.write_bytes(_TINY_PNG)
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _TINY_PNG_B64},
                 "image_path": str(clip_path), "width": 1, "height": 1}
        list(session.turn("look at this", images=[image]))
        session_id, cwd = session.log.session_id, session.cwd

        resumed_log = SessionLog(cwd, session_id=session_id)
        resumed_log._nodes = resumed_log.read_all()
        _system_text, messages, _tools = derive_request(resumed_log, tools=[])
        messages = rehydrate_messages(messages)
        user_msg = next(m for m in messages if m["role"] == "user")
        rebuilt = next(b for b in user_msg["content"] if isinstance(b, dict) and b.get("type") == "image")
        ctx.check(f"the real base64 came back from the saved file, got {rebuilt}",
                  rebuilt.get("source", {}).get("data") == _TINY_PNG_B64)
    finally:
        mock.stop()


@test
def test_no_vision_model_gets_one_notice_and_a_path_mention_never_a_real_image(ctx: Ctx):
    SCENARIOS["img-no-vision"] = _one_shot_text_scenario
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _new_session(fh, mock, model="or:mock/img-no-vision", vision=False)
        clip_path = Path(tempfile.mkdtemp(prefix="halo-clip-")) / "clip-1.png"
        clip_path.write_bytes(_TINY_PNG)
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _TINY_PNG_B64},
                 "image_path": str(clip_path), "width": 1, "height": 1}
        events_ = list(session.turn("look at this", images=[image]))
        notices = [e.data.get("text", "") for e in events_ if e.kind == "notification"]
        ctx.check(f"one plain line says the model does not take images, got {notices}",
                  any("does not take images" in t for t in notices))
        ctx.check("no safety/refusal wording in that line", not any("not allowed" in t for t in notices))
        user_node = next(n for n in session.log.nodes() if n.get("type") == "user")
        ctx.check(f"no image-type block at all was logged, got {user_node['content']}",
                  not any(isinstance(b, dict) and b.get("type") == "image" for b in user_node["content"]))
        ctx.check(f"the saved path is mentioned as plain text instead, got {user_node['content']}",
                  any(isinstance(b, dict) and str(clip_path) in b.get("text", "") for b in user_node["content"]))
        ctx.check("the turn still completed", any(e.kind == "turn_done" for e in events_))
    finally:
        mock.stop()


# ---------------------------------------------------------------------------
# Print mode: `--image <path>` reaches `Session.turn`'s images, proven on
# the real wire body a (stubbed) provider sees -- subprocess + MockUpstream,
# the same pattern tests/test_mcp_e2e.py's own vision test already uses.
# ---------------------------------------------------------------------------

@test
def test_image_flag_reaches_the_request_body_in_print_mode(ctx: Ctx):
    import os
    import subprocess as _subprocess
    fh = build_fake_home()
    # Same technique tests/test_mcp_e2e.py's own vision test uses: the
    # bare mock route has no catalog row of its own, so ModelProfile's
    # default (vision=False) would otherwise exercise the NO-vision
    # path-mention gate instead of the real-image path THIS test is
    # actually about (that gate has its own dedicated test above).
    (fh["home"] / ".halo").mkdir(parents=True, exist_ok=True)
    (fh["home"] / ".halo" / "routes.json").write_text(
        json.dumps({"profiles": {"default": {"vision": True}}}), encoding="utf-8")
    clip_path = fh["proj"] / "shot.png"
    clip_path.write_bytes(_TINY_PNG)
    seen_bodies = []

    def _scn(h, body):
        seen_bodies.append(body)
        _one_shot_text_scenario(h, body)
    SCENARIOS["img-print-mode"] = _scn

    mock = MockUpstream().start()
    try:
        env = dict(os.environ)
        env.pop("BRIDGE_STATE_DIR", None)
        for k in [k for k in env if k.startswith("HALO_")]:
            env.pop(k, None)
        env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                    "OPENROUTER_API_KEY": "test-key", "PYTHONPATH": str(Path(__file__).resolve().parent.parent)})
        args = [sys.executable, "-m", "halo_harness", "-p", "what is this", "--model", "or:mock/img-print-mode",
                "--cwd", str(fh["proj"]), "--image", str(clip_path)]
        result = _subprocess.run(args, env=env, cwd=str(Path(__file__).resolve().parent.parent),
                                  capture_output=True, text=True, timeout=30)
        ctx.check(f"exit 0, got {result.returncode} stderr={result.stderr[-800:]!r}", result.returncode == 0)
        ctx.check(f"at least one upstream request seen, got {len(seen_bodies)}", seen_bodies)
        body_text = json.dumps(seen_bodies[0].get("messages"))
        ctx.check(f"the image's own base64 bytes reached the real request body, got a {len(body_text)}-char body",
                  _TINY_PNG_B64 in body_text)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
