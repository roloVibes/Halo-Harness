"""tests.test_studio_prompt_one -- 3.6.0.2 P6 ("one prompt", the design's F2): what Studio's server sends to a session
names Studio, never the machine's user or host name (P18), and Studio's feed hears the steer and ask kinds (P22, P23).
No browser and no real session: a fake registry row, a fake socket client recording every request.

1. `submit`, `steer`, `answer` and `interrupt` carry `origin: {via: "studio"}` and no `by`, user or host;
2. every command Studio sends (shutdown, pause, resume, an agent's steer, stop and follow, the `fleet.message`
   note) carries `via: "Studio"` and no `by`, user or host;
3. an answer carries `via: studio` by the Prompt panel's route and by the Attention alert's (`live_answer._card`);
4. a hand-off made from Studio writes "Studio" into the brief it leaves in the project folder, never a user or host;
5. `steer_queued`, `steer_applied` and `ask_answered` reach the page (DEFAULT_KINDS, KNOWN_KINDS);
6. an attached session's row carries `follows` and `first_words` (PUBLIC_FIELDS: P27's words, P31's follow).
Run: python -m tests.test_studio_prompt_one
"""
from __future__ import annotations

import getpass
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

SID = "fx6prompt0000000000000000000000a"
ENTRY = {"session_id": SID, "endpoint": "nowhere", "pid": 1, "started": 1.0}
NAME = "owner@gpu-box"  # what harness.name would say; it must reach no request


def _private_words() -> list:
    words = [NAME]
    for fn in (getpass.getuser, socket.gethostname):
        try:
            w = str(fn() or "").strip()
        except Exception:
            w = ""
        if len(w) >= 3:
            words.append(w)
    return words


def _named(fields: dict) -> list:
    """Every way a request could carry a name: a `by` key anywhere, or a private word in its text."""
    blob = json.dumps(fields, default=str)
    found = [w for w in _private_words() if w.lower() in blob.lower()]
    stack = [fields]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            found += ["by"] if "by" in x else []
            stack += list(x.values())
        elif isinstance(x, list):
            stack += x
    return found


class _Sent:
    """The fake socket client and the fake control forward: every request Studio's server sends, in order."""

    def __init__(self):
        self.calls: list = []

    def client(self, entry, timeout):
        sent = self

        class Client:
            def call(self, cmd, **fields):
                sent.calls.append((cmd, fields))
                return {"ok": True, "result": {"accepted": True, "steered": cmd == "steer"}}

            def close(self):
                pass
        return Client()

    def forward(self, sid, cmd, fields):
        self.calls.append((cmd, dict(fields)))
        return 200, {"ok": True}


def _patched(fn):
    """Run `fn(sent, post)` with the session API's live list, socket client and control forward replaced, and
    harness.name set to a user@host name."""
    from halo_harness.studio import live_agents_api as LA
    from halo_harness.studio import live_api as L
    from halo_harness.studio import sessions_api as S
    from halo_harness.studio.api import Request
    sent = _Sent()
    real = (S._list_live, S._client, LA.forward, L._local)
    S._list_live = lambda: [dict(ENTRY)]
    S._client = sent.client
    LA.forward = sent.forward
    L._local = lambda hid: True
    from halo_harness.peers import identity
    from halo_harness.theme import set_config_value
    set_config_value("harness.name", NAME)
    identity.forget_cache()

    def post(path: str, body: dict, params: dict):
        req = Request(method="POST", path=path, query={}, body=body, cwd=Path.cwd(), state_dir=Path.cwd(),
                      server=SimpleNamespace(events=None), params=params)
        return req
    try:
        return fn(sent, post)
    finally:
        S._list_live, S._client, LA.forward, L._local = real


@test
def test_origin_has_no_by_on_submit_steer_answer_interrupt(ctx: Ctx):
    from halo_harness.studio import sessions_api as S

    def run(sent, post):
        for body in ({"cmd": "submit", "text": "hello", "client_id": "pp-p6-1"}, {"cmd": "steer", "text": "turn left"},
                     {"cmd": "answer", "kind": "permission", "request_id": "perm_1", "action": "allow", "scope": "once"},
                     {"cmd": "interrupt"}):
            S.post_command(post(f"sessions/{SID}/command", body, {"sid": SID}))
        return sent.calls
    calls = _patched(run)
    for cmd in ("submit", "steer", "answer", "interrupt"):
        got = [f for c, f in calls if c == cmd]
        ctx.check(f"{cmd} carries origin {{via: studio}} and nothing else, got {got}",
                  len(got) == 1 and got[0].get("origin") == {"via": "studio"})
        ctx.check(f"{cmd} names no one, got {_named(got[0]) if got else None}", bool(got) and not _named(got[0]))


@test
def test_caller_is_via_only_on_every_command(ctx: Ctx):
    from halo_harness.studio import live_agents_api as LA
    from halo_harness.studio import sessions_api as S
    ctx.check(f"caller() is the via only, got {LA.caller()}", LA.caller() == {"via": "Studio"})

    def run(sent, post):
        for body in ({"cmd": "shutdown", "reason": "done"}, {"cmd": "pause"}, {"cmd": "resume"},
                     {"cmd": "note", "text": "hi there"}):
            S.post_command(post(f"sessions/{SID}/command", body, {"sid": SID}))
        for body in ({"cmd": "steer", "text": "focus"}, {"cmd": "stop", "reason": "enough"}, {"cmd": "follow"}):
            LA.post_agent_command(post(f"sessions/{SID}/agents/main/command", body, {"sid": SID, "aid": "main"}))
        return sent.calls
    calls = _patched(run)
    seen = [c for c, _f in calls]
    ctx.check(f"every command was sent, got {seen}", len(calls) == 7 and "note" in seen)
    for cmd, fields in calls:
        ctx.check(f"{cmd} carries via Studio, got {fields}", fields.get("via") == "Studio")
        ctx.check(f"{cmd} names no one, got {_named(fields)}", not _named(fields))


@test
def test_answer_carries_via_studio(ctx: Ctx):
    """One answer by the Prompt panel's route, one by the Attention alert's `_card`: both say Studio sent them, so the
    terminal reads 'Answered in Studio: <label>' (never 'Answered remotely')."""
    from halo_harness.studio import live_answer
    from halo_harness.studio import sessions_api as S

    def run(sent, post):
        S.post_command(post(f"sessions/{SID}/command", {"cmd": "answer", "kind": "permission", "request_id": "perm_1",
                                                         "action": "deny", "message": "not now"}, {"sid": SID}))
        row = {"kind": "permission", "harness": "local", "session_id": SID, "target": {"request_id": "perm_2"}}
        live_answer._card(post("live/attention/answer", {}, {}), row, "a", "")
        return sent.calls
    answers = [f for c, f in _patched(run) if c == "answer"]
    ctx.check(f"two answers sent, got {len(answers)}", len(answers) == 2)
    for f in answers:
        ctx.check(f"answer {f.get('request_id')} carries origin via studio, got {f.get('origin')}",
                  f.get("origin") == {"via": "studio"} and not _named(f))
    from halo_harness.events import answered_line, where_of
    ctx.check("the terminal's line for it reads 'Answered in Studio: Allow'",
              answered_line(where_of((answers[-1].get("origin") or {}).get("via") if answers else ""), "Allow")
              == "Answered in Studio: Allow")


@test
def test_handoff_brief_names_studio_not_a_user_or_host(ctx: Ctx):
    """J3 M3: the brief a hand-off from Studio leaves in the project folder (a file that can be committed)."""
    import inspect

    from halo_harness.studio import live_handoff_api as H
    src = inspect.getsource(H.post_handoff)
    ctx.check("the brief's `by` and its From are Studio, never sources.by or the harness's name (harness.name: user@host)",
              'by, hname = "Studio",' in src and "sources.by(" not in src and 'handoff.brief(harness={**h, "name": by}' in src)
    from halo_harness.live import handoff
    _title, md = handoff.brief(harness={"id": "h1", "name": "Studio"}, session={"session_id": SID},
                               agent={"agent_id": "a1"}, handback="", files=[], by="Studio", to="gpu-box")
    ctx.check(f"the brief reads 'From **Studio**' and 'Handed to **gpu-box** by Studio', no name, got {md[:300]!r}",
              "From **Studio**" in md and "Handed to **gpu-box** by Studio" in md and not _named({"md": md}))


@test
def test_p7_the_brief_names_its_target_by_a_set_name_only(ctx: Ctx):
    """P7 (the checker of P6 batch 1): 'Handed to **<name>**' named the TARGET harness by its harness name, which is
    user@host when no name is set. The brief names its target by the name a person set for it; with none it says
    'another harness' and the folder it works in (the folder's own name, never a path through a home folder).
    Red on 4a150bf9."""
    import inspect

    from halo_harness.studio import live_handoff_api as H
    words = getattr(H, "target_words", None)
    ctx.check("live_handoff_api has target_words (the one place the brief's target is named)", callable(words))
    if not callable(words):
        return
    unset = {"id": "0123456789abcdef", "name": "pat@gpu-box", "user": "pat", "host": "gpu-box",
             "sessions": [{"project": {"root": "/home/pat/work/shop-app"}}]}
    got = words(unset)
    ctx.check(f"no name set (user@host): 'another harness' and its folder, no user or host, got {got!r}",
              got == "another harness, in the folder shop-app" and "pat" not in got and "gpu-box" not in got)
    hub = {"id": "0123456789abcdef", "name": "01234567", "sessions": []}
    ctx.check(f"no name set (the hub's id stand-in), no folder known: 'another harness', got {words(hub)!r}",
              words(hub) == "another harness")
    shaped = {"id": "fedcba9876543210", "name": "pat@gpu-box", "sessions": []}
    ctx.check(f"a user@host-shaped name with no user/host fields is no set name, got {words(shaped)!r}",
              words(shaped) == "another harness")
    named = {"id": "fedcba9876543210", "name": "build-box", "user": "pat", "host": "gpu-box", "sessions": []}
    ctx.check(f"a set name is used, got {words(named)!r}", words(named) == "build-box")
    typed = {"id": "you@studio", "name": "you@studio", "typed": True}
    ctx.check(f"a target not in the view is named by the words he typed, got {words(typed)!r}", words(typed) == "you@studio")
    src = inspect.getsource(H.post_handoff)
    ctx.check("post_handoff names the brief's target through target_words", "to=target_words(target)" in src)


@test
def test_steer_and_ask_kinds_in_default_kinds(ctx: Ctx):
    from halo_harness.studio.feed_kinds import DEFAULT_KINDS
    want = ("steer_queued", "steer_applied", "ask_answered")
    ctx.check(f"the server forwards {want}", all(k in DEFAULT_KINDS for k in want))
    events_ts = (Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "lib" / "events.ts")
    src = events_ts.read_text(encoding="utf-8")
    ctx.check("the page binds them (KNOWN_KINDS)", all(f'"{k}"' in src for k in want))


@test
def test_rows_carry_follows_and_first_words(ctx: Ctx):
    """P27, P31: an ATTACHED session's row (studio/events.py `_pump` through PUBLIC_FIELDS, the `sessions` frame the
    page reads) carries `follows` and `first_words`, as GET sessions' rows do (registry.public_entry)."""
    import halo_harness.remote.client as rc
    from halo_harness.remote.registry import public_entry
    from halo_harness.studio.events import EventBridge

    class OneEvent:  # attaches, then the socket closes: the bridge publishes `attached`, then `detached`
        def __init__(self, *a, **k):
            pass

        def call(self, *a, **k):
            return {"ok": True}

        def next_event(self, timeout):
            raise ConnectionResetError("closed")

        def close(self):
            pass

    entry = dict(ENTRY, follows="fx6old00000000000000000000000000", first_words="fix the parser in the", kind="tui")
    bridge, frames = EventBridge(kinds=["status"], harness_id="h1"), []
    bridge.publish = frames.append
    saved = rc.ControlClient, rc.default_token_for
    rc.ControlClient, rc.default_token_for = OneEvent, (lambda e: "")
    try:
        bridge._pump(entry, __import__("threading").Event())
    finally:
        rc.ControlClient, rc.default_token_for = saved
    attached = next((f for f in frames if (f.get("data") or {}).get("attached") == SID), None)
    rows = ((attached or {}).get("data") or {}).get("sessions") or []
    row = rows[0] if rows else {}
    ctx.check(f"the attached row carries follows, got {row.get('follows')!r}", row.get("follows") == entry["follows"])
    ctx.check(f"the attached row carries first_words, got {row.get('first_words')!r}",
              row.get("first_words") == entry["first_words"])
    listed = public_entry(entry)
    ctx.check("GET sessions' row carries them too", listed.get("follows") == entry["follows"]
              and listed.get("first_words") == entry["first_words"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio prompt one"))
