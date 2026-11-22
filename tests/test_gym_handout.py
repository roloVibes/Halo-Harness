"""tests.test_gym_handout -- 3.6.0.13 GM rules G1 and G2: `halo gym handout`'s job, its two arms and a trial.

G1: the `shop` project the fixed answers are true of; "now" is the measure's own first request on Auto (what a new
session sends) plus the acceptEdits mode line every turn carries; "before" is today's delegate line with the same tools.
G2: a trial sends at most 10 requests through the gym's sender to the module's fake Ollama, answers every call from the
gym's own table over the copy (helpers never run, a path outside refused), and counts with the one meaning of "itself".
A scratch home per test (every environment value put back), never a real model, a real server or the network.
Run: python -m tests.test_gym_handout
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.mock_ollama import MockUpstream, ScriptedByCallCount  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
# tests/test_helpers_words.py:29-41, copied letter for letter (not imported: an independent check of the words)
TODAY_ON = ("- On a big job delegate surveys, searches, test runs and mechanical edits with the Agent tool (`role:` picks "
            "the model table's model), independent pieces in parallel; keep judgement and the final review yourself.")
M1 = ("- Hand work out instead of doing it all yourself: give each part of a job that can run on its own (a search or "
      "survey, a plan, a review, a test run, mechanical edits, a file your model cannot read) to a helper with the Agent "
      "tool; helpers on one job share one `task`; run independent parts in parallel; keep judgement and the final "
      "review yourself.")
M2_CLEAN = ("- Helpers you can start now (`subagent_type`): planner (plan, outline); researcher (research, investigate); "
            "coder (implement, fix, refactor); reviewer (review, audit, judge); writer (summarize, draft, docs, "
            "changelog); media-reader (image, screenshot, video, audio, pdf, transcribe); ops (deploy, release, install, "
            "ci); Judge (pass or fail a result); Tester (run tests, report). With no `subagent_type` Halo picks a kind "
            "from your words.")
M2_HEAD = "- Helpers you can start now (`subagent_type`): "
M3 = "- The Workflow tool lists workflows you can run by `name`: run one when it fits the whole job."
MODE_LINE = "permission mode: acceptEdits (edits in the working directory run without asking; commands ask first)"
REF = "ol:tiny:3b@lan"
MODEL = "tiny:3b"
MOCK_REF = f"ol:{MODEL}@gpu-box"
KEY_NAME = "GPU_BOX_KEY"  # an invented variable and value: the key lives in the scratch home's env file only
KEY = "gym-test-key-0001"
GATEWAY_UNLOAD = (f"unload: gpu-box is a gateway that speaks the OpenAI dialect: the gym cannot unload {MODEL} through "
                  "it; it stays loaded until that host's keep-alive ends.")


def _refuse(handler, body=None) -> None:
    """401 with `WWW-Authenticate: Bearer`, as a host that asks for a key answers a request without it."""
    raw = json.dumps({"error": "unauthorized"}).encode("utf-8")
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("WWW-Authenticate", "Bearer")
    handler.end_headers()
    handler.wfile.write(raw)


def _oai(calls=None, text: str = "") -> list:
    """One OpenAI-dialect streamed reply (chunks), tool calls included."""
    chunks = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
    if text:
        chunks.append({"choices": [{"index": 0, "delta": {"content": text}}]})
    for i, (name, args) in enumerate(calls or []):
        chunks.append({"choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": i, "id": f"call_{i}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]}}]})
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if calls else "stop"}]})
    return chunks


class Gateway:
    """A gateway in front of Ollama that speaks the OpenAI dialect, on loopback: GET /v1/models and POST
    /v1/chat/completions only, with `Authorization: Bearer <key>`; 401 (`WWW-Authenticate: Bearer`) without it, 404 for
    every other path (Ollama's own `/api/...` included). Every request is recorded. A step is a list of chunks or a
    callable(handler, body); steps go by call count, the last repeating. Stopped in `__exit__`."""

    def __init__(self, model: str, steps: list, key: str = KEY):
        import threading
        self.model, self.steps, self.key = model, list(steps), key
        self.requests: list = []
        self.chats = 0
        self._lock = threading.Lock()
        self._server = None

    def __enter__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from tests.helpers.mock_openai import _finish, send_json_response
        gw = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _go(self, method: str) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                try:
                    body = json.loads(raw) if raw else None
                except ValueError:
                    body = None
                with gw._lock:
                    gw.requests.append({"method": method, "path": self.path, "body": body,
                                        "headers": {k.lower(): v for k, v in self.headers.items()}})
                if self.headers.get("Authorization") != f"Bearer {gw.key}":
                    _refuse(self)
                    return
                path = self.path.split("?")[0].rstrip("/")
                if method == "GET" and path == "/v1/models":
                    send_json_response(self, 200, {"object": "list", "data": [{"id": gw.model, "object": "model"}]})
                elif method == "POST" and path == "/v1/chat/completions":
                    with gw._lock:
                        step = gw.steps[min(gw.chats, len(gw.steps) - 1)]
                        gw.chats += 1
                    step(self, body) if callable(step) else _finish(self, step)
                else:
                    send_json_response(self, 404, {"error": "404 page not found"})

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_DELETE(self):
                self._go("DELETE")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def host_entry(self) -> dict:
        return {"name": "gpu-box", "url": self.base_url, "dialect": "openai", "api_key_env": KEY_NAME}

    def chat_bodies(self) -> list:
        return [r["body"] for r in self.requests if r["path"] == "/v1/chat/completions"]

    def native(self) -> list:
        """Every request that went to Ollama's own API."""
        return [f"{r['method']} {r['path']}" for r in self.requests if r["path"].startswith("/api")]


class _Home(ConfigHome):
    """A scratch home whose provider env file is its own (`halo gym` loads it as a session does): the whole process
    environment is put back on the way out, the values that load added included."""

    def __enter__(self):
        self._environ = dict(os.environ)
        super().__enter__()
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
        self.env_file = self.home / "env"
        os.environ["HALO_ENV_FILE"] = str(self.env_file)
        self.copy = self.home / "copy"
        return self

    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            for k in [k for k in os.environ if k not in self._environ]:
                os.environ.pop(k, None)
            for k, v in self._environ.items():
                if os.environ.get(k) != v:
                    os.environ[k] = v


def _texts(messages) -> list:
    out = []
    for m in messages:
        content = m.get("content")
        for b in content if isinstance(content, list) else [{"type": "text", "text": content}]:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(b.get("text"))
    return out


def _without_mode(messages) -> list:
    out = copy.deepcopy(messages)
    for m in out:
        if isinstance(m.get("content"), list):
            m["content"] = [b for b in m["content"] if not (isinstance(b, dict) and b.get("text") == MODE_LINE)]
    return out


# ---- G1 -----------------------------------------------------------------------------------------------------------

@test
def test_the_shop_fixture_holds_what_the_fixed_answers_say(ctx: Ctx):
    from halo_harness import gym_handout_fixture as F
    with _Home() as h:
        folder = F.write(h.copy)
        ctx.check(f"the task is 318 characters, got {len(F.TASK)}", len(F.TASK) == 318)
        reads = []
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if "SHOP_MODE" in line:
                        reads.append((p.relative_to(folder).as_posix(), n))
        ctx.check(f"SHOP_MODE on shop/cart.py:14 and shop/pay.py:22 only, got {reads}",
                  reads == [("shop/cart.py", 14), ("shop/pay.py", 22)])
        funcs = {}
        for name in ("cart", "pay", "ship"):
            tree = ast.parse((folder / "shop" / f"{name}.py").read_text(encoding="utf-8"))
            funcs[name] = [(f.name, ast.get_docstring(f)) for f in tree.body if isinstance(f, ast.FunctionDef)]
        ctx.check(f"4 top-level functions in each, got {funcs}", all(len(v) == 4 for v in funcs.values()))
        ctx.check("none has a docstring", all(d is None for v in funcs.values() for _n, d in v))
        ctx.check("cart.py:14 is inside mode()",
                  "def mode" in (folder / "shop/cart.py").read_text(encoding="utf-8").splitlines()[12])
        ctx.check("pay.py:22 is inside is_test()",
                  "def is_test" in (folder / "shop/pay.py").read_text(encoding="utf-8").splitlines()[20])
        tests = {}
        for p in sorted((folder / "tests").glob("test_*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            tests[p.name] = [f.name for f in tree.body if isinstance(f, ast.FunctionDef) and f.name.startswith("test_")]
        ctx.check(f"4 test functions in 3 files, got {tests}",
                  len(tests) == 3 and sum(len(v) for v in tests.values()) == 4)
        ctx.check("test_refund expects 5.00", "refund(5.00) == 5.00" in (folder / "tests/test_pay.py").read_text("utf-8"))
        spec = importlib.util.spec_from_file_location("gym_shop_pay", folder / "shop" / "pay.py")
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            ctx.check(f"the copy's refund gives 4.50, got {mod.refund(5.00)}", mod.refund(5.00) == 4.5)
        finally:
            sys.modules.pop("gym_shop_pay", None)
        ctx.check("no CHANGES.md", not (folder / "CHANGES.md").exists())
        ctx.check("not a git repository", not (folder / ".git").exists())
        ctx.check("NOTES.md is there", (folder / "NOTES.md").is_file())
        try:
            F.write(folder)
            ctx.check("a folder that is not empty is refused", False)
        except ValueError:
            pass


@test
def test_now_is_the_measures_own_request_on_auto(ctx: Ctx):
    from halo_harness import gym_handout as G
    from halo_harness import gym_handout_fixture as F
    from halo_harness.agent.prompt_measure import _first_request
    with _Home() as h:
        F.write(h.copy)
        for window in (16384, 32768):
            _s, _f, system, messages, sent = G.start(REF, "now", h.copy, window=window, platform="linux")
            _s, _f, r_system, r_messages, r_sent = _first_request(REF, window=window, platform="linux", cwd=h.copy,
                                                                  control="auto", builder=True, text=F.TASK)
            ctx.check(f"{window}: the system text is the measure's", system == r_system)
            ctx.check(f"{window}: the same tools sent, in the same order",
                      [t.get("name") for t in sent] == [t.get("name") for t in r_sent])
            ctx.check(f"{window}: the messages are the measure's plus the mode line",
                      _without_mode(messages) == r_messages and MODE_LINE in _texts(messages)
                      and MODE_LINE not in _texts(r_messages))
            ctx.check(f"{window}: M1 and M2, letter for letter", (M1 + "\n" + M2_CLEAN) in system)
            ctx.check(f"{window}: not today's line", TODAY_ON not in system)


@test
def test_before_is_todays_line_with_the_same_tools(ctx: Ctx):
    from halo_harness import gym_handout as G
    from halo_harness import gym_handout_fixture as F
    from halo_harness.tools.builder_tool import WHEN, WHEN_AUTO
    with _Home() as h:
        F.write(h.copy)
        for window in (16384, 32768):
            before = G.start(REF, "before", h.copy, window=window, platform="linux")
            now = G.start(REF, "now", h.copy, window=window, platform="linux")
            ctx.check(f"{window}: today's line, letter for letter", TODAY_ON in before[2])
            ctx.check(f"{window}: none of M1, M2, M3", M1 not in before[2] and M2_HEAD not in before[2]
                      and M3 not in before[2])
            names = [t.get("name") for t in before[4]]
            ctx.check(f"{window}: the same tool names as now, got {names}", names == [t.get("name") for t in now[4]])
            if window == 32768:
                b = next((t for t in before[4] if t.get("name") == "Builder"), None)
                n = next((t for t in now[4] if t.get("name") == "Builder"), None)
                ctx.check("32768: the Builder is sent in both", b is not None and n is not None)
                if b is not None and n is not None:
                    ctx.check("before: the Builder's WHEN", WHEN in b.get("description", "")
                              and WHEN_AUTO not in b.get("description", ""))
                    ctx.check("now: the Builder's WHEN_AUTO", WHEN_AUTO in n.get("description", ""))


@test
def test_the_task_turn_names_accept_edits(ctx: Ctx):
    from halo_harness import gym_handout as G
    from halo_harness import gym_handout_fixture as F
    with _Home() as h:
        F.write(h.copy)
        for arm in G.ARMS:
            texts = _texts(G.start(REF, arm, h.copy, window=16384, platform="linux")[3])
            ctx.check(f"{arm}: the user's turn is the task", F.TASK in texts)
            ctx.check(f"{arm}: the mode line follows it",
                      F.TASK in texts and MODE_LINE in texts[texts.index(F.TASK) + 1:])


# ---- G2 -----------------------------------------------------------------------------------------------------------

def _reply(calls=None, text: str = "") -> list:
    msg = {"role": "assistant", "content": text}
    if calls:
        msg["tool_calls"] = [{"function": {"name": n, "arguments": a}} for n, a in calls]
    return [{"message": msg, "done": True, "done_reason": "stop", "prompt_eval_count": 30, "eval_count": 10}]


class _Mock:
    """The module's fake Ollama on loopback as the host `gpu-box` of the scratch home's config; stopped in `__exit__`."""

    def __init__(self, h, steps, *, thinks: bool = False, more: "dict | None" = None, key: "str | None" = None):
        caps = ["tools", "thinking"] if thinks else ["tools"]
        self.h, self.key = h, key
        models = {MODEL: steps, **(more or {})}
        self.mock = MockUpstream(
            scenarios={m: self._keyed(ScriptedByCallCount(s)) for m, s in models.items()},
            tags_response={"models": [{"name": m, "model": m, "digest": f"sha256:feed0{i + 1}",
                                       "details": {"family": "tiny", "quantization_level": "Q4_0"}}
                                      for i, m in enumerate(models)]},
            show_responses={m: {"capabilities": caps, "details": {"family": "tiny"},
                                "model_info": {"tiny.context_length": 32768}} for m in models})

    def _keyed(self, scripted):
        """With a key: a chat request without `Authorization: Bearer <key>` is answered 401, as a host that asks for a
        key answers it."""
        if self.key is None:
            return scripted

        def answer(handler, body):
            if handler.headers.get("Authorization") != f"Bearer {self.key}":
                _refuse(handler, body)
                return
            scripted(handler, body)
        return answer

    def __enter__(self):
        self.mock.start()
        host = {"name": "gpu-box", "url": self.mock.base_url}
        if self.key is not None:
            host["api_key_env"] = KEY_NAME
            self.h.env_file.write_text(f"{KEY_NAME}={self.key}\n", encoding="utf-8")
        (self.h.state / "config.json").write_text(json.dumps({"ollama": {"hosts": [host]}}), encoding="utf-8")
        return self.mock

    def __exit__(self, *exc):
        self.mock.stop()


def _chats(mock) -> list:
    return [r["body"] for r in mock.requests if r["path"] == "/api/chat"]


def _wire(body) -> str:
    return json.dumps(body.get("messages") or [], ensure_ascii=False)


def _tool_texts(body) -> list:
    """What the model reads back for each call (an error as the wire marks it for a session: "[tool error] ...")."""
    return [str(m.get("content")).removeprefix("[tool error] ") for m in body.get("messages") or []
            if m.get("role") == "tool"]


def _trial(h, arm: str = "now") -> dict:
    from halo_harness import gym_handout as G
    r = G.resolve(MOCK_REF, state_dir=h.state)
    assert r["error"] is None, r["error"]
    return G.trial(MOCK_REF, arm, h.copy, host=r["host"], route=r["route"], profile=r["profile"],
                   decision=r["decision"], state_dir=h.state, think_off=r["think_off"])


@test
def test_four_calls_hand_out_four_parts(ctx: Ctx):
    from halo_harness import gym_handout_fixture as F
    calls = [("Agent", {"description": "find the readers", "prompt": "List every function that reads SHOP_MODE."}),
             ("Agent", {"description": "add docs", "prompt": "Add a one-line docstring to every function."}),
             ("Agent", {"description": "check", "prompt": "Run the tests and say which fail."}),
             ("Agent", {"description": "write it up", "prompt": "Write CHANGES.md saying what changed."})]
    with _Home() as h, _Mock(h, [_reply(calls), _reply(text="All four done.")]) as mock:
        got = _trial(h)
        ctx.check(f"4 parts in 4 calls, finished, got {got}",
                  got["parts"] == [1, 2, 3, 4] and got["calls"] == 4 and got["bundled"] == 0 and got["finished"]
                  and got["requests"] == 2 and got["error"] is None)
        tool_texts = _tool_texts(_chats(mock)[1])
        ctx.check(f"each call reads its part's answer, letter for letter, got {tool_texts}",
                  tool_texts == list(F.ANSWERS))


@test
def test_one_call_with_all_four_parts_hands_out_one_and_counts_one_bundled(ctx: Ctx):
    from halo_harness import gym_handout_fixture as F
    calls = [("Agent", {"description": "the whole job", "prompt": F.TASK})]
    with _Home() as h, _Mock(h, [_reply(calls), _reply(text="Done.")]) as mock:
        got = _trial(h)
        ctx.check(f"1 part, 1 call, 1 bundled, got {got}",
                  got["parts"] == [1] and got["calls"] == 1 and got["bundled"] == 1 and got["finished"])
        tool_texts = _tool_texts(_chats(mock)[1])
        ctx.check(f"the four answers joined in part order, got {tool_texts}", tool_texts == ["\n".join(F.ANSWERS)])


@test
def test_a_path_outside_the_copy_is_refused(ctx: Ctx):
    from halo_harness import gym_handout_fixture as F
    calls = [("Read", {"file_path": "../outside.txt"}), ("Write", {"file_path": "../x.txt", "content": "x"})]
    with _Home() as h, _Mock(h, [_reply(calls), _reply(text="ok")]) as mock:
        (h.home / "outside.txt").write_text("words from outside the copy", encoding="utf-8")
        got = _trial(h)
        tool_texts = _tool_texts(_chats(mock)[1])
        ctx.check(f"refused both times, got {tool_texts}", tool_texts == [F.OUTSIDE, F.OUTSIDE])
        ctx.check("nothing written outside", not (h.home / "x.txt").exists())
        ctx.check("nothing read outside", "words from outside the copy" not in _wire(_chats(mock)[1]))
        ctx.check(f"own 2, parts 0, got {got}", got["own"] == 2 and got["parts"] == [] and got["calls"] == 0)


@test
def test_an_argument_of_a_wrong_type_is_answered_and_the_trial_goes_on(ctx: Ctx):
    """A local model may send a list where a number or a name belongs: the gym's table answers the call (a failed tool,
    a wrong name), keeps what the trial counted and goes on; the trial is never lost."""
    calls = [("Agent", {"description": "find the readers", "prompt": "List every function that reads SHOP_MODE."}),
             ("Read", {"file_path": "shop/cart.py", "offset": [1]}), ("Read", {"file_path": "shop/cart.py", "limit": {"n": 2}}),
             ("Grep", {"pattern": "SHOP_MODE", "glob": ["*.py"]}), ("Glob", {"pattern": 7}),
             ("Agent", {"subagent_type": ["coder"], "description": "docs", "prompt": "Add a docstring to every function."}),
             ("Workflow", {"name": ["check"], "task": "Run the tests and say which fail."})]
    with _Home() as h, _Mock(h, [_reply(calls), _reply(text="done")]) as mock:
        got = _trial(h)
        tool_texts = _tool_texts(_chats(mock)[1])
        ctx.check(f"the trial finished with its counts kept, got {got}",
                  got["error"] is None and got["finished"] and got["requests"] == 2 and 1 in got["parts"]
                  and got["calls"] == 3 and got["own"] == 4)
        ctx.check(f"every call got an answer (seven), got {len(tool_texts)}: {tool_texts}", len(tool_texts) == 7)
        ctx.check(f"a name of a wrong type is a wrong name: typed 2, right 0, got {got}",
                  got["typed"] == 2 and got["named_right"] == 0 and "Unknown subagent_type" in tool_texts[5])


@test
def test_a_network_path_is_refused_before_the_os_is_asked(ctx: Ctx):
    """The model under test names the paths. A network name (either spelling), a root, a climbing step and a climbing
    Glob pattern are refused as text: no path that names the other host is ever handed to the OS to resolve (on Windows
    that opens a connection to it). A path inside the copy, relative or whole, is still read."""
    import pathlib
    from halo_harness import gym_handout as G
    from halo_harness import gym_handout_fixture as F
    with _Home() as h:
        h.copy.mkdir(parents=True, exist_ok=True)
        F.write(h.copy)
        table = G._Table(h.copy, None, h.state, G._counts())
        asked, real = [], pathlib.Path.resolve

        def spy(self, *a, **k):
            asked.append(str(self))
            return real(self, *a, **k)

        calls = [("Read", {"file_path": "//gpu-box/share/notes.txt"}), ("Read", {"file_path": "\\\\gpu-box\\share\\notes.txt"}),
                 ("Write", {"file_path": "//gpu-box/share/x.txt", "content": "x"}),
                 ("Edit", {"file_path": "\\\\gpu-box\\share\\x.txt", "old_string": "a", "new_string": "b"}),
                 ("Glob", {"pattern": "*", "path": "//gpu-box/share"}), ("Grep", {"pattern": "x", "path": "\\\\gpu-box\\share"}),
                 ("Glob", {"pattern": "//gpu-box/share/*"}), ("Glob", {"pattern": "../*"}), ("Glob", {"pattern": "../../**/*"}),
                 ("Read", {"file_path": "../outside.txt"}), ("Read", {"file_path": "~/outside.txt"})]
        pathlib.Path.resolve = spy
        try:
            got = [table.answer(name, args) for name, args in calls]
            inside = [table.answer("Read", {"file_path": "shop/cart.py"}),
                      table.answer("Read", {"file_path": str(h.copy / "shop" / "cart.py")})]
        finally:
            pathlib.Path.resolve = real
        ctx.check(f"every one refused as outside the copy, got {[g for g in got if g != (F.OUTSIDE, True)]}",
                  all(g == (F.OUTSIDE, True) for g in got))
        ctx.check(f"the OS was never asked about a path that names the other host, got {[p for p in asked if 'gpu-box' in p]}",
                  not any("gpu-box" in p for p in asked))
        ctx.check(f"a path inside the copy is read, by its relative and by its whole name, got {[g[1] for g in inside]}",
                  all(not err and "def " in text for text, err in inside))


@test
def test_a_model_that_cannot_be_resolved_gets_no_card(ctx: Ctx):
    """A local ref whose host is not configured: the cause is printed, no trial runs, no card is written (a card of
    zeros would read as a measurement), and with nothing run the command exits 1."""
    with _Home() as h, _Mock(h, []) as mock:
        ref = f"ol:{MODEL}@nowhere"
        rc, text, _err = _cmd(["handout", ref])
        last = text.strip().splitlines()[-1] if text.strip() else ""
        ctx.check(f"the cause on the model's line, exit 1, got {rc} {last!r}",
                  rc == 1 and last.startswith(f"{ref}: not measured: ") and "nowhere" in last)
        ctx.check(f"no card, no chat request, got {_cards(h)} {len(_chats(mock))}", _cards(h) == [] and _chats(mock) == [])


@test
def test_a_trial_talks_to_the_local_server_only(ctx: Ctx):
    import socket
    seen = []
    real = socket.create_connection

    def watched(address, *a, **kw):
        seen.append(tuple(address[:2]))
        return real(address, *a, **kw)

    with _Home() as h, _Mock(h, [_reply([("Read", {"file_path": "NOTES.md"})]), _reply(text="ok")]) as mock:
        socket.create_connection = watched
        try:
            got = _trial(h)
        finally:
            socket.create_connection = real
        ctx.check(f"the trial ran, got {got}", got["requests"] == 2 and got["finished"] and got["own"] == 1)
        hosts = {(str(a), int(p)) for a, p in seen}
        ctx.check(f"every connection is to the mock on loopback, got {hosts}",
                  bool(hosts) and hosts == {("127.0.0.1", mock.port)})


@test
def test_a_wrong_name_is_refused_and_counted_wrong(ctx: Ctx):
    calls = [("Agent", {"subagent_type": "nobody", "description": "readers", "prompt": "Find SHOP_MODE."})]
    with _Home() as h, _Mock(h, [_reply(calls), _reply(text="ok")]) as mock:
        got = _trial(h)
        tool_texts = _tool_texts(_chats(mock)[1])
        ctx.check(f"the product's refusal words, got {tool_texts}",
                  len(tool_texts) == 1 and tool_texts[0].startswith("Unknown subagent_type 'nobody'. Known types: "))
        ctx.check(f"typed 1, named right 0, parts 0, got {got}",
                  got["typed"] == 1 and got["named_right"] == 0 and got["parts"] == [] and got["calls"] == 1)


@test
def test_ten_requests_end_a_trial_unfinished_and_the_model_is_unloaded(ctx: Ctx):
    from halo_harness import gym_handout as G
    with _Home() as h, _Mock(h, [_reply([("Read", {"file_path": "NOTES.md"})])], thinks=True) as mock:
        got = _trial(h)
        ctx.check(f"exactly 10 requests, unfinished, got {got}",
                  got["requests"] == 10 and not got["finished"] and len(_chats(mock)) == 10 and got["own"] == 10)
        mock.clear()
        card = G.run_model(MOCK_REF, trials=1, state_dir=h.state)
        chats = _chats(mock)
        ctx.check(f"20 chat requests, got {len(chats)} ({card.get('errors')})", len(chats) == 20)
        ctx.check(f"one trial per arm, got {card}", len(card["before"]) == 1 and len(card["now"]) == 1)
        paths = [r["path"] for r in mock.requests]
        unloads = [i for i, r in enumerate(mock.requests) if r["path"] == "/api/generate"
                   and (r["body"] or {}).get("keep_alive") == 0]
        last_chat = max(i for i, p in enumerate(paths) if p == "/api/chat")
        ctx.check(f"one unload (keep_alive 0) after the last chat, got {unloads} (last chat {last_chat})",
                  len(unloads) == 1 and unloads[0] > last_chat)
        ctx.check("thinking off on every chat body", all(b.get("think") is False for b in chats))
        ctx.check(f"4,096 reply tokens on every chat body, got {[(b.get('options') or {}).get('num_predict') for b in chats]}",
                  all((b.get("options") or {}).get("num_predict") == 4096 for b in chats))


@test
def test_identical_arms_run_no_trial(ctx: Ctx):
    from halo_harness import gym_handout as G
    from halo_harness.agent import prompt_wire
    real = prompt_wire._probed_card
    with _Home() as h, _Mock(h, [_reply(text="ok")]) as mock:
        prompt_wire._probed_card = lambda session: {"tools": "none"}
        try:
            card = G.run_model(MOCK_REF, trials=1, state_dir=h.state)
        finally:
            prompt_wire._probed_card = real
        ctx.check(f"same words: no trial, got {card}",
                  card.get("same_words") is True and "before" not in card and "now" not in card)
        ctx.check("no chat request (the model is not loaded)", _chats(mock) == [])
        card = G.run_model(MOCK_REF, trials=1, state_dir=h.state)
        ctx.check(f"unpatched: the trials run, got {card.get('errors')}",
                  "same_words" not in card and len(_chats(mock)) == 2 and len(card["before"]) == 1)


# ---- G3 -----------------------------------------------------------------------------------------------------------
# The design's section 3, letter for letter (the release corrected to 3.6.0.10, the coordinator's ruling)
FACTS = ["Runs one fixed four-part job with each local model you name as main, three times with the words main had "
         "before 3.6.0.10 and three times with today's, and counts the parts it hands to helpers, not whether the work "
         "is better. Helpers are not run: each gets a fixed answer.",
         "Free: local models only; nothing is sent to a cloud.",
         "About 2 minutes per model with three trials when the model runs on a GPU (five real runs took 9 minutes "
         "together); a model that runs on the CPU takes much longer.",
         "A scratch copy of a small project, removed at the end, and one card per model under "
         "~/.halo/gym-handout/<host>/."]
CLOUD = "or:example/model"
SAME = (f"{MODEL}: not measured: this model is sent the same words before and today (it takes no tools, or today's "
        "words do not fit its window), so there is nothing to compare.")


def _cmd(argv, out=None) -> tuple:
    """`halo gym <argv>` in process: (exit code, stdout, stderr); an argparse exit gives its code."""
    import contextlib
    import io
    from halo_harness.gym_cli import cmd_gym
    out = out if out is not None else io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = cmd_gym(list(argv))
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def _cards(h) -> list:
    return sorted(p.relative_to(h.state).as_posix() for p in (h.state / "gym-handout").glob("**/*") if p.is_file())


@test
def test_the_four_facts_print_before_the_first_request(ctx: Ctx):
    import io
    from tests.helpers.mock_ollama import _finish_chat
    out = io.StringIO()
    seen = []

    def first(handler, body):
        seen.append(out.getvalue())
        _finish_chat(handler, _reply(text="ok"))

    rc, text, _err = _cmd(["handout", "--help"])
    ctx.check(f"--help prints the four facts, one per line, got {text!r}",
              rc == 0 and "\n".join(FACTS) in text and "--trials" in text)
    doc = (Path(__file__).resolve().parent.parent / "docs" / "COMMANDS-gym-handout.md").read_text(encoding="utf-8")
    ctx.check("the docs' quoted block holds the four facts, one per line", "\n".join(FACTS) in doc)
    with _Home() as h, _Mock(h, [first, _reply(text="ok")]) as mock:
        rc, _text, _err = _cmd(["handout", MOCK_REF, "--trials", "0"])
        ctx.check(f"--trials 0 is refused by the parser with no request, got {rc} {_err!r}",
                  rc == 2 and "--trials" in _err and mock.requests == [])
        rc, text, err = _cmd(["handout", MOCK_REF], out)
        ctx.check(f"the run ended 0, got {rc} {err!r}", rc == 0)
        ctx.check(f"the four facts were on stdout at the first chat request, got {seen[:1]!r}",
                  len(seen) == 1 and seen[0] == "\n".join(FACTS) + "\n")
        ctx.check(f"three trials per arm by default: 6 chat requests, got {len(_chats(mock))}", len(_chats(mock)) == 6)


@test
def test_a_cloud_ref_is_refused_with_no_request(ctx: Ctx):
    with _Home() as h, _Mock(h, [_reply(text="ok")]) as mock:
        rc, text, _err = _cmd(["handout", CLOUD])
        ctx.check(f"refused, exit 1, got {rc} {text!r}", rc == 1 and text == f"{CLOUD}: the gym runs local models only.\n")
        ctx.check(f"no request of any kind, got {mock.requests}", mock.requests == [])
        ctx.check("no card", _cards(h) == [])
        rc, text, _err = _cmd(["handout", CLOUD, MOCK_REF, "--trials", "1"])
        ctx.check(f"beside a local ref: the cloud line, then the local run, got {rc} {text!r}",
                  rc == 0 and text.startswith(f"{CLOUD}: the gym runs local models only.\n")
                  and len(_chats(mock)) == 2 and len(_cards(h)) == 1)


def _watched_run(ctx, h, argv) -> tuple:
    """Run `halo gym <argv>` with subprocess.Popen and tempfile.mkdtemp watched (both put back in a `finally`)."""
    import subprocess
    import tempfile
    started, made = [], []
    real_popen, real_mkdtemp = subprocess.Popen, tempfile.mkdtemp

    class Watched(real_popen):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            started.append(self)

    def mkdtemp(*a, **kw):
        path = real_mkdtemp(*a, **kw)
        made.append(path)
        return path

    subprocess.Popen, tempfile.mkdtemp = Watched, mkdtemp
    try:
        rc, text, err = _cmd(argv)
    finally:
        subprocess.Popen, tempfile.mkdtemp = real_popen, real_mkdtemp
    copies = [p for p in made if Path(p).name.startswith("halo-gym-")]
    return rc, text, err, started, copies


@test
def test_no_child_is_left_and_the_copy_is_gone(ctx: Ctx):
    from tests.helpers.mock_ollama import send_json

    def fails(handler, body):
        send_json(handler, 500, {"error": "the fake fails this request"})

    for name, steps in (("a run", [_reply([("Read", {"file_path": "NOTES.md"})]), _reply(text="ok")]),
                        ("a run whose chat request fails", [fails])):
        with _Home() as h, _Mock(h, steps) as mock:
            rc, text, err, started, copies = _watched_run(ctx, h, ["handout", MOCK_REF, "--trials", "1"])
            # 3.6.0.14 GR-2: a run no request of which was answered is not measured: exit 1, no card
            ctx.check(f"{name}: exit {0 if name == 'a run' else 1} and a chat request, got {rc} {err!r}",
                      rc == (0 if name == "a run" else 1) and _chats(mock))
            ctx.check(f"{name}: one scratch copy made, got {copies}", len(copies) == 1)
            ctx.check(f"{name}: the copy is gone, got {copies}", not any(Path(p).exists() for p in copies))
            ctx.check(f"{name}: every process the command started has ended, got {started}",
                      all(p.poll() is not None for p in started))
            if name != "a run":
                ctx.check(f"{name}: it says so and keeps no card, got {text!r}",
                          f"\n{MOCK_REF}: not measured: " in text and _cards(h) == [])


@test
def test_the_card_is_written_apart_and_its_line_printed(ctx: Ctx):
    from halo_harness import gym_handout as G
    readers = ("Agent", {"subagent_type": "researcher", "description": "find the readers",
                         "prompt": "List every function that reads SHOP_MODE."})
    docs = ("Agent", {"description": "add docs", "prompt": "Add a one-line docstring to every function."})
    tests_ = ("Agent", {"subagent_type": "coder", "description": "check", "prompt": "Run the tests and say which fail."})
    before = [_reply([("Read", {"file_path": "NOTES.md"})]), _reply(text="done")]
    steps = (before + [_reply([readers, docs]), _reply(text="done")]
             + before + [_reply([tests_]), _reply(text="done")]
             + before + [_reply([readers, docs]), _reply(text="done")])
    with _Home() as h, _Mock(h, steps) as mock:
        rc, text, err = _cmd(["handout", MOCK_REF])
        ctx.check(f"exit 0, 12 chat requests, got {rc} {len(_chats(mock))} {err!r}", rc == 0 and len(_chats(mock)) == 12)
        ctx.check(f"one card, under gym-handout/<host>/, named by the digest, got {_cards(h)}",
                  _cards(h) == ["gym-handout/gpu-box/handout-feed01.json"])
        ctx.check("nothing under the battery's folder", not (h.state / "gym").exists())
        card = json.loads((h.state / "gym-handout" / "gpu-box" / "handout-feed01.json").read_text(encoding="utf-8"))
        expected = (f"{MODEL}: hands out 1.7 of 4 parts in 1.7 calls (before 0) · bundled 0 · names right 3 of 3 · "
                    "own steps 0 (before 1) · finished 3 of 3 (before 3) · 3 trials")
        ctx.check(f"the line, letter for letter, got {G.line(card)!r}", G.line(card) == expected)
        # 3.6.0.14 GR-2: a line per trial before it, the verdict under it
        import re
        trials = "".join(f"  {arm} {i} of 3: {got} · \\d+ s\n" for i, (b, n) in enumerate(
            [("0 of 4 parts in 0 calls · own steps 1 · finished", "2 of 4 parts in 2 calls · own steps 0 · finished"),
             ("0 of 4 parts in 0 calls · own steps 1 · finished", "1 of 4 parts in 1 call · own steps 0 · finished"),
             ("0 of 4 parts in 0 calls · own steps 1 · finished", "2 of 4 parts in 2 calls · own steps 0 · finished")],
            1) for arm, got in (("before", b), ("now", n)))
        verdict = "  Verdict: passes. Today's words make it hand out 1.7 more of 4 parts."
        ctx.check(f"printed after the facts, a line per trial, then the line and the verdict, got {text!r}",
                  re.fullmatch(re.escape("\n".join(FACTS) + "\n") + trials + re.escape(f"{expected}\n{verdict}\n"),
                               text) is not None)
        one = {**card, "trials": 1, "before": card["before"][:1], "now": card["now"][1:2],
               "errors": ["now 1: the fake failed", "unload: none"]}
        ctx.check(f"at --trials 1 the 3s follow, and the errors line follows the card's, got {G.line(one)!r}",
                  G.line(one) == f"{MODEL}: hands out 1 of 4 parts in 1 call (before 0) · bundled 0 · names right 1 "
                                 "of 1 · own steps 0 (before 1) · finished 1 of 1 (before 1) · 1 trial\n"
                                 "  errors during the run (non-fatal): now 1: the fake failed; unload: none")


@test
def test_a_model_sent_the_same_words_is_not_measured(ctx: Ctx):
    from halo_harness.agent import prompt_wire
    real = prompt_wire._probed_card
    with _Home() as h, _Mock(h, [_reply(text="ok")]) as mock:
        prompt_wire._probed_card = lambda session: {"tools": "none"}
        try:
            rc, text, err = _cmd(["handout", MOCK_REF])
        finally:
            prompt_wire._probed_card = real
        ctx.check(f"exit 0, got {rc} {err!r}", rc == 0)
        ctx.check(f"the not-measured line after the facts, got {text!r}", text == "\n".join(FACTS) + "\n" + SAME + "\n")
        ctx.check(f"no card, got {_cards(h)}", _cards(h) == [])
        ctx.check("no chat request", _chats(mock) == [])


# ---- 3.6.0.14 GR-1: the gym reaches a host the way a session does -------------------------------------------------
FOUR = [("Agent", {"description": "find the readers", "prompt": "List every function that reads SHOP_MODE."}),
        ("Agent", {"description": "add docs", "prompt": "Add a one-line docstring to every function."}),
        ("Agent", {"description": "check", "prompt": "Run the tests and say which fail."}),
        ("Agent", {"description": "write it up", "prompt": "Write CHANGES.md saying what changed."})]


def gateway_home(h, gw) -> None:
    """The scratch home's one host is `gw` (a gateway with the OpenAI dialect); its key is in the home's env file only."""
    (h.state / "config.json").write_text(json.dumps({"ollama": {"hosts": [gw.host_entry()]}}), encoding="utf-8")
    h.env_file.write_text(f"{KEY_NAME}={gw.key}\n", encoding="utf-8")


@test
def test_a_key_kept_in_the_env_file_reaches_the_host(ctx: Ctx):
    """A native host entry whose key is named by `api_key_env`, its value only in the env file: the gym loads that file
    as a session does, every chat request carries the bearer and the trials run; the key is printed nowhere."""
    with _Home() as h, _Mock(h, [_reply(FOUR), _reply(text="All four done.")] * 2, key=KEY) as mock:
        ctx.check("the key is not in the process environment before the run", KEY_NAME not in os.environ)
        rc, text, err = _cmd(["handout", MOCK_REF, "--trials", "1"])
        chats = [r for r in mock.requests if r["path"] == "/api/chat"]
        ctx.check(f"four chat requests, each with the bearer, got {[r['headers'].get('authorization') for r in chats]}",
                  len(chats) == 4 and all(r["headers"].get("authorization") == f"Bearer {KEY}" for r in chats))
        ctx.check(f"the trials ran: exit 0, a card, no error, got {rc} {text!r} {err!r}",
                  rc == 0 and len(_cards(h)) == 1 and "errors during the run" not in text)
        card_text = "".join((h.state / c).read_text(encoding="utf-8") for c in _cards(h))
        ctx.check("the key is in neither the output nor the card", KEY not in text + err + card_text)


@test
def test_a_gateway_with_the_openai_dialect_is_spoken_to_in_it(ctx: Ctx):
    """A host entry with `dialect: "openai"` and a key: the trials go through /v1/chat/completions with the bearer,
    the counts are right, no request goes to Ollama's own API, and the card says the model could not be unloaded."""
    from halo_harness import gym_handout as G
    steps = [_oai(FOUR), _oai(text="All four done.")] * 2
    with _Home() as h, Gateway(MODEL, steps) as gw:
        gateway_home(h, gw)
        rc, text, err = _cmd(["handout", MOCK_REF, "--trials", "1"])
        bodies = gw.chat_bodies()
        ctx.check(f"exit 0, four chat requests, got {rc} {len(bodies)} {err!r} {text[-400:]!r}",
                  rc == 0 and len(bodies) == 4)
        # The one GET of /api/ps a background model listing may make (models_best_at -> ollama_panel.analyze_host,
        # as in every session on such a host; it reads "nothing loaded" from the refusal) is not the gym's
        ctx.check(f"no request of the gym's to Ollama's own API, got {gw.native()}",
                  [p for p in gw.native() if p != "GET /api/ps"] == [])
        ctx.check("every request carries the entry's key",
                  all(r["headers"].get("authorization") == f"Bearer {KEY}" for r in gw.requests))
        ctx.check("the model's own name, and no Ollama-only field (think) on the wire",
                  all(b.get("model") == MODEL and "think" not in b for b in bodies))
        cards = G.iter_cards(h.state)
        now = (cards[0]["now"] if cards else [{}])[0]
        ctx.check(f"4 parts in 4 calls, finished, got {now}",
                  now.get("parts") == [1, 2, 3, 4] and now.get("calls") == 4 and now.get("finished"))
        ctx.check(f"the card's errors are the one unload sentence, got {cards[0].get('errors') if cards else None}",
                  bool(cards) and cards[0]["errors"] == [GATEWAY_UNLOAD])
        ctx.check("the key is printed nowhere", KEY not in text + err)


# ---- 3.6.0.14 GR-2: the command tells the truth about its run ---------------------------------------------------------
def _last_lines(text: str, n: int) -> list:
    return text.rstrip("\n").splitlines()[-n:]


@test
def test_a_run_nobody_answered_is_not_measured(ctx: Ctx):
    """Every chat request refused: the run stops after the first trial of each arm (two requests, not six), the model
    is not measured (its cause once), no card is written and the command exits 1."""
    import re
    with _Home() as h, _Mock(h, [_refuse]) as mock:
        rc, text, err = _cmd(["handout", MOCK_REF])
        last = _last_lines(text, 1)[0]
        ctx.check(f"exit 1, got {rc} {err!r}", rc == 1)
        ctx.check(f"two chat requests (the early stop), got {len(_chats(mock))}", len(_chats(mock)) == 2)
        ctx.check(f"no card and no file under gym-handout, got {_cards(h)}", _cards(h) == [])
        m = re.fullmatch(re.escape(f"{MOCK_REF}: not measured: ") + r"(.+) \(2 trials\)", last)
        ctx.check(f"the not-measured line names the cause once for both trials, got {last!r}",
                  m is not None and "before 1" not in last and "now 1" not in last)
        ctx.check(f"the cause is printed once in the whole output, got {text!r}",
                  m is not None and text.count(m.group(1)) == 1)
        trials = [ln for ln in text.splitlines() if ln.startswith("  ")]
        ctx.check(f"a line per trial that ran, each says no answer, got {trials}",
                  len(trials) == 2 and all(re.fullmatch(r"  (before|now) 1 of 3: 0 of 4 parts in 0 calls · own steps 0 · "
                                                        r"no answer · \d+ s", ln) for ln in trials))


@test
def test_of_two_models_the_answered_one_gets_its_card(ctx: Ctx):
    other = "small:1b"
    done = [_reply([("Read", {"file_path": "NOTES.md"})]), _reply(text="ok")] * 2
    with _Home() as h, _Mock(h, [_refuse], more={other: done}) as mock:
        rc, text, err = _cmd(["handout", MOCK_REF, f"ol:{other}@gpu-box", "--trials", "1"])
        ctx.check(f"exit 0 (one model ran), got {rc} {err!r}", rc == 0)
        ctx.check(f"the first is not measured, got {text!r}", f"\n{MOCK_REF}: not measured: " in text)
        ctx.check(f"the second has its line and its card only, got {_cards(h)}",
                  f"\n{other}: hands out " in text and _cards(h) == ["gym-handout/gpu-box/handout-feed02.json"])
        ctx.check(f"two chat requests for the first (the early stop), four for the second, got {len(_chats(mock))}",
                  len(_chats(mock)) == 6)


@test
def test_a_trial_with_no_answer_is_left_out_of_the_means(ctx: Ctx):
    """One trial of six gets no answer: the means count the answered trials only, the errors line names it, and the
    verdict says to run it again."""
    own = [_reply([("Read", {"file_path": "NOTES.md"})]), _reply(text="done")]
    four = [_reply(FOUR), _reply(text="done")]
    steps = own + four + own + [_refuse] + own + four
    with _Home() as h, _Mock(h, steps) as mock:
        rc, text, err = _cmd(["handout", MOCK_REF])
        ctx.check(f"exit 0, 11 chat requests, a card, got {rc} {len(_chats(mock))} {_cards(h)} {err!r}",
                  rc == 0 and len(_chats(mock)) == 11 and len(_cards(h)) == 1)
        head, verdict, errors = _last_lines(text, 3)
        ctx.check(f"the means count the two answered trials, got {head!r}",
                  head.startswith(f"{MODEL}: hands out 4 of 4 parts in 4 calls (before 0) · ")
                  and "finished 2 of 3 (before 3)" in head)
        ctx.check(f"the verdict, word for word, got {verdict!r}",
                  verdict == "  Verdict: none. 1 of 6 trials got no answer: run it again.")
        ctx.check(f"the errors line names now 2, got {errors!r}",
                  errors.startswith("  errors during the run (non-fatal): now 2: "))


@test
def test_one_line_per_trial_as_each_ends(ctx: Ctx):
    import io
    import re
    from tests.helpers.mock_ollama import _finish_chat
    out = io.StringIO()
    seen = []

    def now_first(handler, body):
        seen.append(out.getvalue())
        _finish_chat(handler, _reply(FOUR))

    own = [_reply([("Read", {"file_path": "NOTES.md"})]), _reply(text="done")]
    steps = own + [now_first, _reply(text="done")] + own + [_reply([FOUR[0]]), _reply(text="done")]
    with _Home() as h, _Mock(h, steps):
        rc, text, err = _cmd(["handout", MOCK_REF, "--trials", "2"], out)
        ctx.check(f"exit 0, got {rc} {err!r}", rc == 0)
        trials = [ln for ln in text.splitlines() if ln.startswith("  ") and not ln.startswith("  Verdict")]
        pattern = [r"  before 1 of 2: 0 of 4 parts in 0 calls · own steps 1 · finished · \d+ s",
                   r"  now 1 of 2: 4 of 4 parts in 4 calls · own steps 0 · finished · \d+ s",
                   r"  before 2 of 2: 0 of 4 parts in 0 calls · own steps 1 · finished · \d+ s",
                   r"  now 2 of 2: 1 of 4 parts in 1 call · own steps 0 · finished · \d+ s"]
        ctx.check(f"one line per trial, in order, word for word, got {trials}",
                  len(trials) == 4 and all(re.fullmatch(p, ln) for p, ln in zip(pattern, trials)))
        ctx.check(f"each before the model's line, got {text!r}",
                  text.index("  now 2 of 2: ") < text.index(f"{MODEL}: hands out "))
        ctx.check(f"before 1's line was out when now 1 asked, got {seen!r}",
                  len(seen) == 1 and re.search(r"\n  before 1 of 2: .* s\n$", seen[0]) is not None)
        card = json.loads((h.state / _cards(h)[0]).read_text(encoding="utf-8"))
        ctx.check(f"every trial and the card keep their seconds, got {card.get('seconds')}",
                  isinstance(card.get("seconds"), (int, float))
                  and all(isinstance(t.get("seconds"), (int, float)) for t in card["before"] + card["now"]))


def _t(parts=0, calls=0, typed=0, right=0, finished=True, requests=2, error=None) -> dict:
    return {"parts": list(range(1, parts + 1)), "calls": calls, "bundled": 0, "typed": typed, "named_right": right,
            "own": 0, "proposals": 0, "finished": finished, "requests": requests, "error": error}


@test
def test_the_verdict_says_whether_the_model_passes(ctx: Ctx):
    from halo_harness import gym_handout as G

    def card(before, now) -> dict:
        return {"model": MODEL, "trials": len(now), "before": before, "now": now, "errors": []}

    cases = [
        ("passes", card([_t(1, 1)] * 3, [_t(3, 3, 3, 3)] * 3),
         "  Verdict: passes. Today's words make it hand out 2 more of 4 parts."),
        ("no more parts", card([_t(1, 1)] * 3, [_t(1, 1), _t(2, 2), _t(1, 1)]),
         "  Verdict: does not pass. Today's words do not make it hand out more (1.3 of 4 parts, before 1)."),
        ("names wrong", card([_t()] * 3, [_t(2, 2, 10, 8)] * 3),
         "  Verdict: does not pass. It names a helper right in 24 of 30 calls (it needs 9 in 10)."),
        ("finishes fewer", card([_t()] * 3, [_t(2, 2), _t(2, 2, finished=False, requests=10), _t(2, 2)]),
         "  Verdict: does not pass. It finishes fewer trials with today's words (2 of 3, before 3)."),
        ("two reasons", card([_t()] * 3, [_t(0, 0, 0, 0), _t(1, 1, 1, 0), _t(0, 0, finished=False, requests=10)]),
         "  Verdict: does not pass. Today's words do not make it hand out more (0.3 of 4 parts, before 0). It names a "
         "helper right in 0 of 1 calls (it needs 9 in 10). It finishes fewer trials with today's words (2 of 3, "
         "before 3)."),
        ("no answer", card([_t(), _t(requests=1, finished=False, error="x")], [_t(2, 2)] * 2),
         "  Verdict: none. 1 of 4 trials got no answer: run it again."),
    ]
    for name, c, want in cases:
        ctx.check(f"{name}: got {G.verdict(c)!r}", G.verdict(c) == want)
    answered = card([_t(), _t(requests=3, finished=False, error="x")], [_t(2, 2)] * 2)
    ctx.check("a trial that got answers before its error was answered", "Verdict: none" not in G.verdict(answered))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
