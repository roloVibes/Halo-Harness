"""tests.test_round_0e_concierge_media -- Halo 2.0.7 round 0e: the
concierge (one secretary that is also the eyes) + the one media agent.

  * `roles.concierge` resolves through the real role table; unset (or
    resolving to the session model) means NO concierge and every feature
    degrades to the pre-0e behavior;
  * `/ask`'s `ask_concierge`: a one-shot call over the deterministic
    history digest -- never through the session log, never waking the
    orchestrator;
  * the eyes: images arriving on a BLIND active model get concierge
    descriptions folded into the turn as a `concierge_vision` snapshot;
    no concierge -> the old path-mention behavior, byte for byte;
  * the notice digest: a pending-notice block reaches the model as
    frame + concierge digest with the verbatim block archived in a meta
    node (never model-visible); no concierge -> round-0b verbatim;
  * the Media tool: deterministic ffmpeg frame extraction (real files,
    real ffmpeg on PATH) + metadata; the media agent bio loads.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
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


def _new_session(*, mock, model, small_model=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    cwd = Path(tempfile.mkdtemp(prefix="r0e-e2e-"))
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="r0e-home-")))
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    return Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="r0e-state-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
        agents={}, routes={},
        small_model_ref=(parse_model_ref(small_model) if small_model else None),
    )


def _set_concierge_role(raw: str) -> None:
    """Write roles.concierge into the scoped home's config.json (the same
    file `resolve_role_ref`'s table reads -- `bridge_home()`/config.json,
    note the `.halo` component BRIDGE_TEST_HOME alone does not include)."""
    from halo_harness.config.paths import bridge_home
    cfg_path = bridge_home() / "config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    roles = dict(cfg.get("roles") or {})
    roles["concierge"] = raw
    cfg["roles"] = roles
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")


# ---- role resolution -------------------------------------------------------------


@test
def test_concierge_resolves_only_when_configured(ctx: Ctx):
    from halo_harness.concierge import resolve_concierge

    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0e-main")
        ctx.check("unset role -> no concierge", resolve_concierge(session) is None)
        _set_concierge_role("or:mock/r0e-concierge")
        resolved = resolve_concierge(session)
        ctx.check("configured role -> (ref, profile)", resolved is not None)
        if resolved:
            ctx.check("the ref is the role's model", resolved[0].raw == "or:mock/r0e-concierge")
        # A concierge pointing at the SESSION model is "no concierge" (it
        # would wake the orchestrator).
        _set_concierge_role("or:mock/r0e-main")
        ctx.check("role == session model -> no concierge",
                  resolve_concierge(session) is None)
    finally:
        mock.stop()


# ---- /ask: the secretary -----------------------------------------------------------


@test
def test_ask_concierge_answers_from_the_digest_without_touching_the_log(ctx: Ctx):
    SCENARIOS["r0e-main"] = ScriptedTurns([_text_step("the main answer")])
    SCENARIOS["r0e-concierge"] = ScriptedTurns([_text_step("2 rounds done, all green")])
    mock = MockUpstream().start()
    try:
        from halo_harness.concierge import ask_concierge
        session = _new_session(mock=mock, model="or:mock/r0e-main")
        _set_concierge_role("or:mock/r0e-concierge")
        evs = list(session.turn("start the work"))
        n_before = len(session.log.nodes())
        answer = ask_concierge(session, "what has been done so far?")
        ctx.check("the concierge answered", "green" in answer)
        ctx.check("the /ask exchange NEVER touched the session log",
                  len(session.log.nodes()) == n_before)
        ctx.check("no user node carries the question",
                  not [n for n in session.log.nodes() if n.get("type") == "user"
                       and "what has been done" in str(n.get("content"))])
    finally:
        mock.stop()


# ---- the eyes ------------------------------------------------------------------------


@test
def test_blind_model_gets_concierge_image_descriptions(ctx: Ctx):
    SCENARIOS["r0e-blind"] = ScriptedTurns([_text_step("noted the screenshot")])
    SCENARIOS["r0e-eyes"] = ScriptedTurns([_text_step("a terminal window showing a test run, all green")])
    mock = MockUpstream().start()
    try:
        # The ACTIVE model must be blind (ModelProfile() default) and the
        # concierge must claim vision -- patched at resolve time.
        import halo_harness.model as model_mod
        from halo_harness.model import ModelProfile
        real_resolve = model_mod.resolve_model_profile

        def _eyes_profile(ref, state_dir, routes):
            if "r0e-eyes" in (getattr(ref, "raw", "") or ""):
                return ModelProfile(vision=True, context_tokens=128000)
            return real_resolve(ref, state_dir, routes)

        model_mod.resolve_model_profile = _eyes_profile
        try:
            session = _new_session(mock=mock, model="or:mock/r0e-blind")
            _set_concierge_role("or:mock/r0e-eyes")
            png = Path(tempfile.mkdtemp(prefix="r0e-img-")) / "shot.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)  # opaque bytes; the mock never looks
            evs = list(session.turn("look at this", images=[{"type": "image", "path": str(png)}]))
        finally:
            model_mod.resolve_model_profile = real_resolve
        notes = [e.data.get("text", "") for e in evs if e.kind == "notification"]
        ctx.check("the eyes notification fired",
                  any("concierge described" in t for t in notes))
        snap_kinds = [(n.get("kind"), (n.get("content") or [{}])[0].get("text", ""))
                      for n in session.log.nodes() if n.get("type") == "snapshot"]
        ctx.check("a concierge_vision snapshot landed",
                  any(k == "concierge_vision" and "terminal window" in t for k, t in snap_kinds))
        # The blind model still got the path mention, not an image block.
        user_nodes = [n for n in session.log.nodes() if n.get("type") == "user"]
        blocks = [b for n in user_nodes for b in (n.get("content") or [])]
        ctx.check("no image block reached the blind model's log",
                  not [b for b in blocks if isinstance(b, dict) and b.get("type") == "image"])
    finally:
        mock.stop()


@test
def test_blind_model_without_concierge_keeps_the_old_behavior(ctx: Ctx):
    SCENARIOS["r0e-blind2"] = ScriptedTurns([_text_step("ok")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0e-blind2")
        png = Path(tempfile.mkdtemp(prefix="r0e-img-")) / "shot.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        evs = list(session.turn("look at this", images=[{"type": "image", "path": str(png)}]))
        notes = [e.data.get("text", "") for e in evs if e.kind == "notification"]
        ctx.check("the old path-mention notification, unchanged",
                  any("does not take images; attached as a path" in t for t in notes))
        ctx.check("no concierge_vision snapshot",
                  not [n for n in session.log.nodes()
                       if n.get("type") == "snapshot" and n.get("kind") == "concierge_vision"])
    finally:
        mock.stop()


# ---- the notice digest -----------------------------------------------------------------


@test
def test_pending_notices_are_digested_and_archived(ctx: Ctx):
    SCENARIOS["r0e-main3"] = ScriptedTurns([_text_step("noted")])
    SCENARIOS["r0e-digester"] = ScriptedTurns([_text_step("job X passed; job Y failed -- needs a retry")])
    mock = MockUpstream().start()
    try:
        from halo_harness.agent.derive import derive_request
        session = _new_session(mock=mock, model="or:mock/r0e-main3")
        _set_concierge_role("or:mock/r0e-digester")
        session._pending_job_notices.append(
            "[Background job bash_x (run tests) finished, exit code 1]\nFAILED: 2 tests\nthe details ...")
        evs = list(session.turn("continue"))
        status_evs = [e for e in evs if e.kind == "status_notice"]
        ctx.check("the notice was delivered", len(status_evs) == 1)
        framed = status_evs[0].data.get("framed", "")
        ctx.check("the model-visible block carries the DIGEST",
                  "concierge digest" in framed and "needs a retry" in framed)
        ctx.check("the full body is NOT model-visible",
                  "FAILED: 2 tests" not in framed)

        _, messages, _ = derive_request(session.log)
        joined = json.dumps([m.get("content") for m in messages], ensure_ascii=False)
        ctx.check("derived request carries the digest, not the body",
                  "needs a retry" in joined and "FAILED: 2 tests" not in joined)

        meta = [n for n in session.log.nodes() if n.get("type") == "meta"
                and "archived_notice" in n]
        ctx.check("the verbatim block is archived in a meta node", len(meta) == 1)
        if meta:
            ctx.check("the archive holds the full text",
                      "FAILED: 2 tests" in meta[0]["archived_notice"])
    finally:
        mock.stop()


@test
def test_pending_notices_without_concierge_stay_verbatim(ctx: Ctx):
    SCENARIOS["r0e-main4"] = ScriptedTurns([_text_step("noted")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0e-main4")
        session._pending_job_notices.append(
            "[Background job bash_y (run tests) finished, exit code 1]\nFAILED: 2 tests")
        evs = list(session.turn("continue"))
        status_evs = [e for e in evs if e.kind == "status_notice"]
        ctx.check("delivered verbatim (round 0b)",
                  len(status_evs) == 1 and "FAILED: 2 tests" in status_evs[0].data.get("framed", ""))
        ctx.check("no archive meta node without a concierge",
                  not [n for n in session.log.nodes() if n.get("type") == "meta"
                       and "archived_notice" in n])
    finally:
        mock.stop()


# ---- the media tool + bio -----------------------------------------------------------------


@test
def test_media_tool_extracts_real_frames_with_ffmpeg(ctx: Ctx):
    import shutil
    if not shutil.which("ffmpeg"):
        # GitHub's hosted runners ship no ffmpeg -- a host without it
        # skips (the tool's own "install ffmpeg" error line is what users
        # see), never fails the round.
        from tests.helpers.runner import SkipTest
        raise SkipTest("ffmpeg not on PATH on this host")
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.media import MediaTool

    scratch = Path(tempfile.mkdtemp(prefix="r0e-media-"))
    # A real 2-second test video via ffmpeg itself (testsrc).
    video = scratch / "clip.mp4"
    r = subprocess_run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", "testsrc=duration=2:size=160x120:rate=5",
                        "-pix_fmt", "yuv420p", "-y", str(video)])
    ctx.check("fixture video built", r.returncode == 0 and video.exists())
    if not video.exists():
        return
    ctx_media = ToolContext(cwd=scratch, session_dir=scratch, tool_use_id="tu_media_1")
    result = MediaTool().run({"path": str(video), "frames": 3}, ctx_media)
    ctx.check("extraction succeeded", not result.is_error)
    frames = sorted((scratch / "media" / "tu_media_1").glob("frame_*.png"))
    ctx.check(f"3 frames on disk, got {len(frames)}", len(frames) == 3)
    ctx.check("the result names the frames",
              all(p.name in result.content for p in frames))
    ctx.check("the result carries the video summary", "160x120" in result.content)

    missing = MediaTool().run({"path": str(scratch / "nope.mp4")}, ctx_media)
    ctx.check("a missing file is a clean error", missing.is_error and "No such file" in missing.content)


def subprocess_run(argv):
    import subprocess
    return subprocess.run(argv, capture_output=True, text=True, timeout=90.0, check=False)


@test
def test_media_agent_bio_loads_and_is_sane(ctx: Ctx):
    from halo_harness.agents_yaml import load_agent_bio_raw
    bio = load_agent_bio_raw("media")
    ctx.check("the bio resolves", bio is not None)
    if not bio:
        return
    ctx.check("it allows Media and Read (the describe loop)",
              "Media" in (bio.get("tools", {}).get("allow") or [])
              and "Read" in (bio.get("tools", {}).get("allow") or []))
    ctx.check("its preference is a vision-capable lane",
              "flash" in (bio.get("models", {}).get("preference") or ""))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
