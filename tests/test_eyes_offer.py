"""tests.test_eyes_offer -- Halo 3.3.6.0 R6: the offer before the eyes (agent/eyes_offer.py, agent/eyes_turn.py) in
a real Session against the OpenAI-shaped mock upstream (no model is called):

1. a model that cannot see and no visual lane, nobody to ask: one line, the text alone with the image as its path,
   the old notice, the ladder's "eyes" rung logged;
2. a visual lane set: this turn switches to it (the image rides as an image), the turn's end switches back;
3. the description: a model that sees describes the image into the turn (an `eyes_vision` snapshot, the log's
   meta names who saw it), chosen with the image (Studio's button);
4. interactive: the card (an approval_request at position "eyes" with the three choices, what each does), the
   session row's `eyes` while it waits, answered "send";
5. a model that sees: no offer; a local model nothing says sees is offered, a cloud one is not;
6. a steer with an image while a turn runs: it lands at the steer's safe point (the offer first when the model
   cannot see, the chip's choice riding on the image);
7. the TUI's menu (tui/widgets/eyes_card.py): Enter takes the first that can run, a disabled one takes no key.
Run: python -m tests.test_eyes_offer
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vision" / "shot.png"


def _text(text: str) -> list:
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}, {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


class Rig:
    """A scoped home, the mock, `or:mock/ey-blind` (no vision) as the session model, `or:mock/ey-eyes` seeing."""

    def __enter__(self):
        import halo_harness.model as M
        self.saved_home = os.environ.get("BRIDGE_TEST_HOME")
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="ey-offer-home-")
        SCENARIOS["ey-blind"] = ScriptedTurns([_text("noted")])
        SCENARIOS["ey-eyes"] = ScriptedTurns([_text("a terminal with a red failing test")])
        self.mock = MockUpstream().start()
        self.real = M.resolve_model_profile

        def profile(ref, state_dir, routes=None):
            if "ey-eyes" in (getattr(ref, "raw", "") or ""):
                return M.ModelProfile(vision=True, context_tokens=128000)
            return self.real(ref, state_dir, routes)
        M.resolve_model_profile = profile
        return self

    def __exit__(self, *exc):
        import halo_harness.model as M
        M.resolve_model_profile = self.real
        self.mock.stop()
        for k in ("ey-blind", "ey-eyes"):
            SCENARIOS.pop(k, None)
        if self.saved_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = self.saved_home

    def session(self, model="or:mock/ey-blind", vision=False):
        from halo_harness.agent.assemble import SessionContext
        from halo_harness.agent.loop import Session
        from halo_harness.model import ModelProfile, parse_model_ref
        from halo_harness.permissions import PermissionEngine
        from halo_harness.providers.stream import ProviderCreds
        cwd = Path(tempfile.mkdtemp(prefix="ey-offer-cwd-"))
        return Session(cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(vision=vision),
                       creds=ProviderCreds(base_url=self.mock.base_url, api_key="k"),
                       state_dir=Path(tempfile.mkdtemp(prefix="ey-offer-state-")), model_label=model,
                       session_context=SessionContext(cwd=cwd, model_label=model, bare=True),
                       openrouter_base_url=self.mock.base_url, max_turns=10,
                       permission_engine=PermissionEngine(mode="auto", cwd=cwd), agents={}, routes={})

    def image(self, **extra) -> dict:
        from halo_harness.agent.image_attach import image_block_from_path
        return {**image_block_from_path(FIXTURE), **extra}

    def models(self) -> list:
        return [(r.get("body") or {}).get("model") for r in self.mock.requests if r.get("body")]


def _role(name: str, raw: str) -> None:
    from halo_harness.theme import set_config_value
    set_config_value(f"roles.{name}", raw)


def _user_blocks(session) -> list:
    return [b for n in session.log.nodes() if n.get("type") == "user" for b in (n.get("content") or [])]


def _markers(evs) -> list:
    return [e.data.get("text") or e.data.get("line") or "" for e in evs if e.kind == "turn_marker" and e.data.get("state") == "ladder"]


@test
def test_no_lane_nobody_to_ask_the_text_alone_and_the_rung(ctx: Ctx):
    from halo_harness.agent.degrade import ledger_rungs
    with Rig() as rig:
        s = rig.session()
        evs = list(s.turn("look at this", images=[rig.image()]))
        notes = [e.data.get("text", "") for e in evs if e.kind == "notification"]
        ctx.check(f"the old notice stays, got {notes}", any("does not take images; attached as a path" in t for t in notes))
        marks = _markers(evs)
        ctx.check(f"one ladder line names the fact and the choice, got {marks}", len(marks) == 1 and
                  "or:mock/ey-blind cannot see images (declared" in marks[0] and "the text alone" in marks[0] and "the default" in marks[0])
        rungs = ledger_rungs(s) or []
        ctx.check(f"the eyes rung is logged like any other, got {rungs}", rungs and rungs[-1]["rung"] == "eyes"
                  and rungs[-1]["trigger"] == "needs-eyes")
        blocks = _user_blocks(s)
        ctx.check("no image block, the path as text", not [b for b in blocks if b.get("type") == "image"]
                  and any(str(FIXTURE) in str(b.get("text")) for b in blocks))
        ctx.check("no wording that blocks", not any("not allowed" in m or "safety" in m for m in marks + notes))


@test
def test_the_visual_lane_for_this_turn_then_back(ctx: Ctx):
    with Rig() as rig:
        s = rig.session()
        _role("visual", "or:mock/ey-eyes")
        evs = list(s.turn("look at this", images=[rig.image()]))
        marks = _markers(evs)
        ctx.check(f"the line says this turn on the lane, got {marks}", marks and "this turn on or:mock/ey-eyes (the visual lane)" in marks[0])
        switch = [e.data.get("text") for e in evs if e.kind == "turn_marker" and e.data.get("state") == "switch"]
        ctx.check(f"the switch says it is the eyes, got {switch[:1]}", switch and "this turn sees through or:mock/ey-eyes" in switch[0])
        blocks = _user_blocks(s)
        img = [b for b in blocks if b.get("type") == "image"]
        ctx.check(f"the image rides as an image (its path in the log, no bytes), got {img}", img and img[0].get("image_path") == str(FIXTURE)
                  and "source" not in img[0])
        ctx.check(f"the call went to the lane, got {rig.models()}", "mock/ey-eyes" in rig.models())
        ctx.check(f"back on the session's model after the turn, got {s.model_ref.raw}", s.model_ref.raw == "or:mock/ey-blind")


@test
def test_a_model_that_sees_describes_it_into_the_turn(ctx: Ctx):
    from halo_harness.agent import eyes_offer as O
    with Rig() as rig:
        s = rig.session()
        saved = O.describer
        O.describer = lambda session: {"ref": "or:mock/ey-eyes", "why": "auto: it sees"}
        try:
            evs = list(s.turn("what failed?", images=[rig.image(eyes_choice="describe")]))
        finally:
            O.describer = saved
        snaps = [n for n in s.log.nodes() if n.get("type") == "snapshot" and n.get("kind") == "eyes_vision"]
        text = (snaps[0].get("content") or [{}])[0].get("text", "") if snaps else ""
        ctx.check(f"the description lands as text, got {text[:160]!r}", "a terminal with a red failing test" in text
                  and "or:mock/ey-eyes looked at the image" in text)
        meta = [n.get("eyes") for n in s.log.nodes() if n.get("type") == "meta" and n.get("eyes")]
        ctx.check(f"the log says who saw it, got {meta}", meta and meta[0]["seen_by"] == "or:mock/ey-eyes" and meta[0]["images"] == [str(FIXTURE)])
        marks = _markers(evs)
        ctx.check(f"chosen with the image, got {marks}", marks and "describes the image into the turn (chosen with the image)" in marks[0])
        ctx.check("the session model kept", s.model_ref.raw == "or:mock/ey-blind")


@test
def test_interactive_the_card_and_its_answer(ctx: Ctx):
    with Rig() as rig:
        s = rig.session()
        s.interactive = True
        _role("visual", "or:mock/ey-eyes")
        out: list = []
        t = threading.Thread(target=lambda: out.extend(s.turn("look", images=[rig.image()])), daemon=True)
        t.start()
        deadline = time.time() + 20
        while time.time() < deadline and not getattr(s, "_eyes_pending", None):
            time.sleep(0.05)
        pending = dict(getattr(s, "_eyes_pending", None) or {})
        ids = [c["id"] for c in pending.get("choices") or []]
        ctx.check(f"the card waits with three choices, got {ids}", ids == ["lane", "describe", "send"] and pending.get("default") == "lane")
        lane = (pending.get("choices") or [{}])[0]
        ctx.check(f"each says what it does and costs, got {lane}", "switches this turn to or:mock/ey-eyes" in lane.get("what", "")
                  and "writes nothing" in lane.get("what", ""))
        ctx.check("the line", "cannot see images" in pending.get("line", ""))
        ok = s.resolve_approval(pending.get("id"), {"action": "send", "instruction": None})
        t.join(20)
        ctx.check(f"answered, the turn ends, got ok={ok}", ok and not t.is_alive() and any(e.kind == "turn_done" for e in out))
        req = [e for e in out if e.kind == "approval_request"]
        ctx.check("an approval_request at position eyes", req and req[0].data.get("position") == "eyes")
        ctx.check("the card is gone", getattr(s, "_eyes_pending", None) is None)
        ctx.check("the text alone", "the text alone" in (_markers(out) or [""])[0] and "the default" not in (_markers(out) or [""])[0])


@test
def test_who_is_offered(ctx: Ctx):
    from halo_harness.agent import eyes_offer as O
    with Rig() as rig:
        s = rig.session(model="or:mock/ey-eyes", vision=True)
        evs = list(s.turn("look", images=[rig.image()]))
        ctx.check("a model that sees: no offer", not _markers(evs) and any(b.get("type") == "image" for b in _user_blocks(s)))
    from halo_harness.model import parse_model_ref
    local = SimpleNamespace(model_ref=parse_model_ref("ol:mystery:7b@lab"), model_profile=SimpleNamespace(vision=False))
    local._eyes_fact = ("ol:mystery:7b@lab", {"value": None, "truth": None, "source": "nothing says"})
    ctx.check("a local model nothing says sees is offered", O.needs_offer(local) is not None
              and O.model_line(local, O.needs_offer(local)).startswith("nothing says whether ol:mystery:7b@lab can see images"))
    cloud = SimpleNamespace(model_ref=parse_model_ref("or:mock/x"), model_profile=SimpleNamespace(vision=False))
    cloud._eyes_fact = ("or:mock/x", {"value": None, "truth": None, "source": "the catalog does not say"})
    ctx.check("a cloud model nothing says about: the image is sent", O.needs_offer(cloud) is None)


@test
def test_a_steer_with_an_image_lands_at_its_safe_point(ctx: Ctx):
    with Rig() as rig:
        s = rig.session(model="or:mock/ey-eyes", vision=True)
        ctx.check("idle: no steer to queue", s.steer("see this", images=[rig.image()]) is False)
        s._busy.set()
        try:
            ok = s.steer("see this", images=[rig.image()])
            writes = list(s._pending_worker_writes)
        finally:
            s._busy.clear()
            s._pending_worker_writes, s._steer_queue = [], []
        ctx.check(f"queued for the steer's safe point, got {[w[0] for w in writes]}", ok and writes and writes[0][0] == "eyes_steer"
                  and writes[0][1]["images"][0]["image_path"] == str(FIXTURE))
        s._pending_worker_writes = list(writes)
        evs = list(s._apply_pending_steers_events(1))
        snap = [n for n in s.log.nodes() if n.get("type") == "snapshot" and n.get("kind") == "steer_image"]
        ctx.check(f"a model that sees: its LOG shape, the path and no bytes, got {snap[-1:]}", snap and snap[-1]["content"][0] ==
                  {"type": "image", "image_path": str(FIXTURE), "media_type": "image/png", "width": 4, "height": 3})
        ctx.check("no offer for it", not _markers(evs))
    with Rig() as rig:
        s = rig.session()
        s._pending_worker_writes = [("eyes_steer", {"images": [rig.image(eyes_choice="send")]})]
        evs = list(s._apply_pending_steers_events(1))
        snap = [n for n in s.log.nodes() if n.get("type") == "snapshot" and n.get("kind") == "steer_image"]
        ctx.check(f"a blind model mid-turn: the chip's choice, the path as text, the rung, got {snap[-1:]} {_markers(evs)}",
                  snap and snap[-1]["content"][0]["type"] == "text" and str(FIXTURE) in snap[-1]["content"][0]["text"]
                  and _markers(evs) and "chosen with the image" in _markers(evs)[0])


@test
def test_the_tui_menu(ctx: Ctx):
    from halo_harness.tui.widgets.eyes_card import EyesCard
    got: list = []
    opts = [{"id": "lane", "label": "no visual lane set", "what": "set one", "disabled": True},
            {"id": "describe", "label": "let or:mock/ey-eyes describe it", "what": "one call"},
            {"id": "send", "label": "send the text without it", "what": "no extra call"}]
    card = EyesCard(request_id="eyes-1", text="m cannot see images (declared: x)", choices=opts, on_decide=got.append)
    lines = card.menu_lines()
    ctx.check(f"each choice says what it does, the one that cannot run takes no key, got {lines}",
              lines[0].strip().startswith("no visual lane set") and "[2] let or:mock/ey-eyes describe it: one call" in lines[1])
    card.action_choose("lane")
    ctx.check("a disabled choice is not taken", got == [])
    card.action_choose_first()
    ctx.check(f"Enter: the first that can run, once, got {got}", got == [{"action": "describe", "instruction": None}])
    card.action_choose("send")
    ctx.check("one decision only", len(got) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
