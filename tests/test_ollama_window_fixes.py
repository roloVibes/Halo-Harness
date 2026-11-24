"""tests.test_ollama_window_fixes -- Halo 3.6.0.0 R8 fix pass: the window a call asks of an Ollama server, against a
fake that cuts a prompt longer than its window the way the real server does.

Every end-to-end test runs a real `halo -p` (tests/helpers/halo_turn_net.py) against
`tests/helpers/mock_ollama_loads.LoadCountingOllama` on loopback: never a real Ollama, never a real model.

Pinned (the judge's findings on R8, brief v360-R8-judge):
- S7 (second pass F1): the fake cuts a prompt longer than `num_ctx` the way Ollama 0.40.16 was measured to: one
  over-long message to `num_ctx // 2 + 2`, a chat by dropping whole messages from the front; both answer 200 and
  "stop"; a reply that runs out of room stops with `done_reason: "length"`;
- M1: a loaded window is held only when the prompt (a 15 % margin) and the reply's room at that window fit; a count
  at the window's end is a cut prompt, sent again once at a window that holds it, with one line; the reply's room in
  a held window is never squeezed under the window's own;
- S4: a session that takes more turns loads once, at the largest window; a one-shot run with a small prompt asks
  small; a one-shot run that grows reloads once, straight to the largest window;
- S1: a loaded window the recorded truth says spills to the CPU is not held: one reload under it, one line why;
- S2: a failed `/api/ps` read is unknown: no "loading" claim, nothing stored, the window last used is kept;
- S3: the learned token ratio takes no count a reused prefix may have shortened;
- S10: the read after a call is one per turn, at its end, and a server that stops answering adds at most 1 s.
Run: python -m tests.test_ollama_window_fixes
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

import subprocess  # noqa: E402

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.mock_ollama_loads import GB, LoadCountingOllama  # noqa: E402
from tests import test_ollama_loads as L  # noqa: E402

MODEL, CAP = L.MODEL, L.CAP
test, TESTS = new_registry()
_BASE: dict = {}


def _opts(fake) -> list:
    return [(b.get("options") or {}) for b in L._turn_chats(fake)]


def _fit(fh) -> dict:
    p = Path(fh["home"]) / ".halo" / "ollama-fit.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _run(fh, fake, *args: str, stdin: str = None, timeout: float = 180):
    cmd = [sys.executable, "-m", "tests.helpers.halo_turn_net", *args, "--model", f"ol:{MODEL}@gpu-box",
           "--cwd", str(fh["proj"]), "--permission-mode", "auto"]
    return subprocess.run(cmd, env=L._env(fh, fake), cwd=str(L.REPO_DIR), capture_output=True, text=True,
                          input=stdin, timeout=timeout, encoding="utf-8", errors="replace")


def _ask(fh, fake, prompt: str, *extra: str):
    """`halo -p` with the prompt on stdin (a padded prompt is past a Windows command line's length)."""
    return _run(fh, fake, "-p", *extra, stdin=prompt)


def _baseline() -> "tuple[int, int]":
    """(Halo's estimate, the fake's real count) of the plain one-word prompt: the scale the padded prompts use."""
    if not _BASE:
        fake = L._fake()
        try:
            fh = L._home(fake)
            L._run(fh, fake)
            line = (L._turn_lines(fh) or [{}])[-1]
            _BASE.update(est=int(line.get("estimate_tokens") or 4000), real=int(line.get("prompt_eval_count") or 4000))
        finally:
            fake.stop()
    return _BASE["est"], _BASE["real"]


def _padded(target_est: int) -> str:
    est0, _real0 = _baseline()
    return "Reply with exactly one word: ready. Context follows. " + "word " * max(0, int((target_est - est0) * 3.5 / 5))


def _ok(ctx, result, what: str) -> None:
    L._ok(ctx, result, what)


# ---- S7: the fake cuts like the real server ------------------------------------------------------------------------

def _chat(fake, num_ctx: int, chars: int, messages: list = None, **opts) -> dict:
    body = {"model": MODEL, "stream": True, "options": {"num_ctx": num_ctx, **opts},
            "messages": messages or [{"role": "user", "content": "x" * chars}]}
    req = urllib.request.Request(fake.base_url + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        lines = [json.loads(x) for x in resp.read().decode("utf-8").splitlines() if x.strip()]
    return lines[-1]


@test
def test_the_fake_cuts_a_prompt_the_way_the_real_server_does(ctx: Ctx):
    # the shapes measured on Ollama 0.40.16 (one message: num_ctx // 2 + 2 at 2,048 / 4,096 / 8,192; 61 messages:
    # 2,020 at 2,048 and 4,012 at 4,096 -- whole messages dropped from the front), done_reason "stop" for both
    fake = L._fake()
    try:
        for window in (2048, 4096, 8192):
            last = _chat(fake, window, 34000)  # one message of about 9.4k tokens
            ctx.check(f"one over-long message at {window}: read as {window // 2 + 2}, got {last}",
                      last.get("prompt_eval_count") == window // 2 + 2 and last.get("done_reason") == "stop")
        many = [{"role": "system", "content": "You answer."}] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": "y" * 560} for i in range(60)]
        for window in (2048, 4096):
            last = _chat(fake, window, 0, messages=many)  # 61 messages, about 10k tokens
            got = last.get("prompt_eval_count") or 0
            ctx.check(f"61 messages at {window}: whole messages dropped from the front, a little under it, got {last}",
                      window - 200 < got <= window and last.get("done_reason") == "stop")
        ctx.check(f"every cut is counted, got {len(fake.cuts)}", len(fake.cuts) == 5)
        fake.reply_tokens = 9000
        last = _chat(fake, 8192, 400)
        room = 8192 - last.get("prompt_eval_count", 0)
        ctx.check(f"a reply longer than the room left stops at the window: length, got {last}",
                  last.get("done_reason") == "length" and last.get("eval_count") == room)
        last = _chat(fake, 32768, 400, num_predict=100)
        ctx.check(f"a reply past num_predict stops there: length, 100, got {last}",
                  last.get("done_reason") == "length" and last.get("eval_count") == 100)
    finally:
        fake.stop()


# ---- M1: the loaded window holds a request only with the ladder's need ---------------------------------------------

@test
def test_a_loaded_window_the_prompt_nearly_fills_is_not_held_and_nothing_is_cut(ctx: Ctx):
    est0, real0 = _baseline()
    fake = L._fake()
    fake.count_ratio = 1.13 / (real0 / est0)  # the real count 13 % over the estimate (inside the 15 % deadband)
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 16384)
        result = _ask(fh, fake, _padded(15000))
        _ok(ctx, result, "a near-full loaded window")
        ctx.check(f"no prompt was cut, got {fake.cuts}", not fake.cuts)
        sent = _opts(fake)
        ctx.check(f"the call asked for more than the loaded 16,384, got {sent}", bool(sent) and sent[-1].get("num_ctx", 0) > 16384)
        lines = L._turn_lines(fh)
        ctx.check(f"no ledger line is a cut prompt, got {[(x.get('num_ctx_sent'), x.get('prompt_eval_count')) for x in lines]}",
                  bool(lines) and not any(x.get("trimmed") for x in lines))
    finally:
        fake.stop()


@test
def test_the_reply_room_is_never_squeezed_by_a_loaded_window(ctx: Ctx):
    est0, real0 = _baseline()
    fake = L._fake()
    fake.count_ratio = 1.0 / (real0 / est0)
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 16384)
        result = _ask(fh, fake, _padded(13000))  # fits 16,384 with 1,024 to spare, not with the window's room
        _ok(ctx, result, "a prompt in the squeeze band")
        sent = _opts(fake)
        got = sent[-1] if sent else {}
        window, room = got.get("num_ctx") or 0, got.get("num_predict") or 0
        ctx.check(f"the reply's room ({room}) is the window's own (at least min(window/4, 4096)) at {window}",
                  room >= min(window // 4, 4096))
        ctx.check(f"so the window grew past 16,384, got {window}", window > 16384)
    finally:
        fake.stop()


@test
def test_a_prompt_the_window_cut_is_sent_again_once_at_a_window_that_holds_it(ctx: Ctx):
    est0, real0 = _baseline()
    fake = L._fake()
    fake.count_ratio = 4.0 / (real0 / est0)  # the estimate is 4x under the real count: the first window cuts it
    try:
        fh = L._home(fake)
        result = L._run(fh, fake, "Reply with exactly one word: ready", "--verbose")
        _ok(ctx, result, "a cut prompt")
        sent = _opts(fake)
        ctx.check(f"exactly one cut, got {fake.cuts}", len(fake.cuts) == 1)
        ctx.check(f"sent twice: once cut, once again, got {sent}", len(sent) == 2)
        if len(sent) == 2:
            ctx.check(f"the second time at the largest window {CAP}, got {sent[1].get('num_ctx')}",
                      sent[1].get("num_ctx") == CAP)
        said = [ln for ln in result.stdout.splitlines() if "about half the 16k window" in ln and "re-sent" in ln]
        ctx.check(f"one line says so, got {said} in {result.stdout[-800:]!r}", len(said) == 1)
        lines = L._turn_lines(fh)
        ctx.check(f"the ledger marks the cut call trimmed, got {[x.get('trimmed') for x in lines]}",
                  bool(lines) and lines[0].get("trimmed") is True and lines[-1].get("trimmed") is False)
    finally:
        fake.stop()


# ---- S4: one load per session, straight to the largest window ------------------------------------------------------

def _user(text: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def _session(fh, fake, turns: list, timeout: float = 300) -> "tuple[int, int]":
    """A `--input-format stream-json` session driven the way a client does: each user line after the previous
    turn's `result` (a line sent while a turn runs is a steer into that turn). Returns (exit code, results seen)."""
    cmd = [sys.executable, "-m", "tests.helpers.halo_turn_net", "-p", "--input-format", "stream-json",
           "--output-format", "stream-json", "--verbose", "--model", f"ol:{MODEL}@gpu-box", "--cwd", str(fh["proj"]),
           "--permission-mode", "auto"]
    proc = subprocess.Popen(cmd, env=L._env(fh, fake), cwd=str(L.REPO_DIR), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                            errors="replace")
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    results = 0
    try:
        for line in turns:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            for out in proc.stdout:
                if out.startswith("{") and '"type": "result"' in out:
                    results += 1
                    break
        proc.stdin.close()
        proc.stdout.read()
        return proc.wait(), results
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()


@test
def test_an_interactive_session_of_60k_tokens_is_one_load(ctx: Ctx):
    fake = L._fake()
    try:
        fh = L._home(fake, max_ctx=131072)
        pad = "word " * int(25000 * 3.5 / 5)
        turns = [_user("Reply with exactly one word: ready"), _user("Context follows. " + pad),
                 _user("More context follows. " + pad + pad[: len(pad) // 5])]
        rc, results = _session(fh, fake, turns)
        ctx.check(f"a three-turn session: exit 0 and three results, got {rc} {results}", rc == 0 and results == 3)
        sent = _opts(fake)
        ctx.check(f"three calls, got {len(sent)}", len(sent) == 3)
        ctx.check(f"one load, got {fake.loads}", len(fake.loads) == 1)
        ctx.check(f"at the largest window it may use (131,072), got {[o.get('num_ctx') for o in sent]}",
                  bool(sent) and all(o.get("num_ctx") == 131072 for o in sent))
        ctx.check(f"nothing cut, got {fake.cuts}", not fake.cuts)
        last = (L._turn_lines(fh) or [{}])[-1]
        ctx.check(f"the last turn is about 60k tokens, got {last.get('prompt_eval_count')}",
                  (last.get("prompt_eval_count") or 0) > 50000)
    finally:
        fake.stop()


@test
def test_a_one_shot_with_a_small_prompt_asks_small(ctx: Ctx):
    fake = L._fake()
    try:
        fh = L._home(fake)
        _ok(ctx, L._run(fh, fake), "a one-shot run")
        sent = _opts(fake)
        ctx.check(f"one call at a ladder step of 16,384 or less, got {sent}",
                  len(sent) == 1 and sent[0].get("num_ctx") in (8192, 16384))
    finally:
        fake.stop()


def _tools_sent(body: dict) -> "tuple[list, int]":
    """(the tool names a chat body sends, their tokens as the diet counts them: chars / 3.5 of each wire tool)."""
    from halo_harness.agent.prompt_composition import tokens_of
    tools = [t for t in body.get("tools") or [] if isinstance(t, dict)]
    return [(t.get("function") or {}).get("name") or t.get("name") for t in tools], sum(tokens_of(t) for t in tools)


@test
def test_a_one_shot_asked_at_16384_sends_the_tool_block_of_that_window(ctx: Ctx):
    """3.6.0.12 OS: the diet of a one-shot's first ask is shaped for the window it asks (prompt_diet.tools_budget:
    2,200 tokens at 16,384), not for the cap; the tools left out are ToolSearch's, which is sent."""
    fake = L._fake()
    try:
        fh = L._home(fake)
        _ok(ctx, L._run(fh, fake), "a one-shot run")
        first = (L._turn_chats(fake) or [{}])[0]
        names, tokens = _tools_sent(first)
        asked = (first.get("options") or {}).get("num_ctx")
        ctx.check(f"the first ask is 16,384, got {asked}", asked == 16384)
        ctx.check(f"its tool block is at most 2,200 tokens, got {tokens:,} ({len(names)} tools)", tokens <= 2200)
        ctx.check(f"ToolSearch is among the tools sent, got {names}", "ToolSearch" in names)
    finally:
        fake.stop()


@test
def test_a_one_shot_on_auto_reads_the_helpers_lines_and_asks_16384(ctx: Ctx):
    """3.6.0.12 OS: `halo -p` on a local model on Auto reads the two lines every session on Auto reads (when to hand
    work out, the helpers it can start), not the old single line, and its first ask is still 16,384."""
    from halo_harness.agent.helpers_words import M1, M2_HEAD
    fake = L._fake()
    try:
        fh = L._home(fake)
        _ok(ctx, L._run(fh, fake), "a one-shot run on Auto")
        first = (L._turn_chats(fake) or [{}])[0]
        system = next((m.get("content") or "" for m in first.get("messages") or [] if m.get("role") == "system"), "")
        asked = (first.get("options") or {}).get("num_ctx")
        ctx.check("the system text holds when to hand work out (M1)", M1 in system)
        ctx.check("the system text holds the helpers it can start (M2)", M2_HEAD in system)
        ctx.check("not the old single line", "On a big job delegate surveys" not in system)
        ctx.check(f"the first ask is 16,384, got {asked}", asked == 16384)
    finally:
        fake.stop()


@test
def test_a_one_shot_that_grows_reloads_once_to_the_largest_window(ctx: Ctx):
    fake = L._fake()
    try:
        fh = L._home(fake)
        files = []
        for name in ("a.txt", "b.txt", "c.txt"):
            p = Path(fh["proj"]) / name
            p.write_text("".join(f"line {i:05d} " + "x" * 58 + "\n" for i in range(350)), encoding="utf-8")
            files.append(str(p))
        fake.replies = [{"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "Read", "arguments": {"file_path": f}}}]} for f in files]
        result = L._run(fh, fake, "Read the three files, then reply with exactly one word: ready")
        _ok(ctx, result, "a growing one-shot run")
        sent = _opts(fake)
        ctx.check(f"four calls (three reads, the answer), got {len(sent)}", len(sent) == 4)
        ctx.check(f"at most two loads: the first, then one reload, got {[x['num_ctx'] for x in fake.loads]}",
                  len(fake.loads) <= 2)
        if len(fake.loads) == 2:
            ctx.check(f"the reload went to the largest window {CAP}, got {fake.loads[1]['num_ctx']}",
                      fake.loads[1]["num_ctx"] == CAP)
        ctx.check(f"nothing cut, got {fake.cuts}", not fake.cuts)
    finally:
        fake.stop()


# ---- S1: a loaded window that spills is not held -------------------------------------------------------------------

@test
def test_a_loaded_window_that_spills_to_the_cpu_is_reloaded_under_it_once(ctx: Ctx):
    fake = L._fake()

    def vram(num_ctx):
        size = GB + num_ctx * 64 * 1024
        return size, (size if num_ctx < 32768 else size // 2)
    fake.vram[MODEL] = vram
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 32768)  # loaded by another client at a window that runs partly on the CPU
        outs = []
        for i in range(3):
            result = L._run(fh, fake, "Reply with exactly one word: ready", "--verbose")
            _ok(ctx, result, f"run {i}")
            outs.append(result.stdout)
        sent = [o.get("num_ctx") for o in _opts(fake)]
        ctx.check(f"one reload in three runs, got {fake.loads}", len(fake.loads) == 1)
        ctx.check(f"once the spill is known, never 32,768 again, got {sent}", 32768 not in sent[1:])
        ctx.check(f"the reload is under the spill, got {fake.loads}", bool(fake.loads) and fake.loads[0]["num_ctx"] < 32768)
        said = [o for o in outs if "partly on the CPU" in o]
        ctx.check(f"one run (the one that reloads) says why, got {[o[-300:] for o in outs]!r}", len(said) == 1)
    finally:
        fake.stop()


def _spilling_fake():
    """The fake of the spill test: a window of 32,768 or more runs half on the CPU; preloaded there."""
    fake = L._fake()

    def vram(num_ctx):
        size = GB + num_ctx * 64 * 1024
        return size, (size if num_ctx < 32768 else size // 2)
    fake.vram[MODEL] = vram
    return fake


@test
def test_a_one_shot_over_half_of_the_spill_window_is_sent_the_window_the_line_names(ctx: Ctx):
    # 3.6.0.12 OS: a prompt of about 8,400 tokens: twice it is past 16,384, but it and the reply's room fit 16,384.
    # The line says "reloaded at 16k" and 16,384 is what is sent (it was 32,768, the window that spills).
    prompt = _padded(8400)
    fake = _spilling_fake()
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 32768)
        result = _ask(fh, fake, prompt, "--verbose")
        _ok(ctx, result, "a one-shot of about 8,400 tokens")
        sent = [o.get("num_ctx") for o in _opts(fake)]
        ctx.check(f"the window sent is 16,384, got {sent}", bool(sent) and sent[0] == 16384)
        ctx.check(f"the reload is at 16,384, got {fake.loads}", [x["num_ctx"] for x in fake.loads] == [16384])
        out = result.stdout
        ctx.check(f"the line names 16k, got {out[-600:]!r}", "reloaded at 16k" in out)
        ctx.check(f"one sentence says the prompt is more than half of it, got {out[-600:]!r}",
                  "the prompt is more than half of it: the reply has 4,096 tokens" in out)
        ctx.check(f"no line names the 32,768 window as the one sized, got {out[-600:]!r}", "32,768 window" not in out)
        ctx.check(f"3.6.0.19 LM: one line says the reply's room (that sentence), got {out[-600:]!r}",
                  "the reply's room is" not in out)
    finally:
        fake.stop()


def _session_said(fh, fake, turns: list, timeout: float = 300, between=None) -> "tuple[int, int, str]":
    """`_session`'s client with `--output-format text --verbose`, so the `↳` lines a person reads are printed: each
    user line after the previous turn's end line (`◼ ...`). Returns (exit code, turns ended, everything printed).
    `between(i)`, when given, runs after turn i (from 1) ended, before the next line is sent."""
    cmd = [sys.executable, "-m", "tests.helpers.halo_turn_net", "-p", "--input-format", "stream-json",
           "--output-format", "text", "--verbose", "--model", f"ol:{MODEL}@gpu-box", "--cwd", str(fh["proj"]),
           "--permission-mode", "auto"]
    proc = subprocess.Popen(cmd, env=L._env(fh, fake), cwd=str(L.REPO_DIR), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                            errors="replace")
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    ended, out = 0, []
    try:
        for line in turns:
            if between is not None and ended:
                between(ended)
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            for got in proc.stdout:
                out.append(got)
                if "◼ " in got:
                    ended += 1
                    break
        proc.stdin.close()
        out.append(proc.stdout.read())
        return proc.wait(), ended, "".join(out)
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()


def _tool_names(tools) -> list:
    """The names of a tool block, from a request body (`{"function": {"name"}}`) or a shaped request (`{"name"}`)."""
    return [(t.get("function") or {}).get("name") or t.get("name") for t in tools or [] if isinstance(t, dict)]


def _measured_names(fh, window: int, text: str) -> list:
    """The product's own measure (agent/prompt_measure._first_request) of a NEW session of more turns in this fake home
    at `window`, its first user message `text`, no Builder (a `-p` run): the names of the tools its first request
    sends. The process's home is put back after."""
    import os
    from halo_harness.agent.prompt_measure import _first_request
    keys = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")
    was = {k: os.environ.get(k) for k in keys}
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    try:
        sent = _first_request(f"ol:{MODEL}@gpu-box", window=window, platform=sys.platform, cwd=fh["proj"],
                              one_shot=False, builder=False, text=text)[4]
    finally:
        for k, v in was.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return _tool_names(sent)


def _chat_tool_names(fake) -> list:
    """The tool names of every `/api/chat` request that carries tools, in order."""
    return [_tool_names(b.get("tools")) for b in (r["body"] or {} for r in fake.requests
            if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat") if b.get("tools")]


def _plain_session_names(window: int, texts: list) -> list:
    """The tool names of every request of a session of more turns on the plain fake (nothing spills) whose host's
    max_ctx is `window`: what a session on a model of that window is sent."""
    fake = L._fake()
    try:
        fh = L._home(fake, max_ctx=window)
        rc, ended, _out = _session_said(fh, fake, [_user(t) for t in texts], timeout=300)
        if rc != 0 or ended != len(texts):
            raise AssertionError(f"the plain session at {window:,} did not end: {rc} {ended}")
        return _chat_tool_names(fake)
    finally:
        fake.stop()


@test
def test_a_session_under_the_spill_is_sent_the_window_the_line_names_every_turn(ctx: Ctx):
    """3.6.0.19 LM: a session of more turns (stream-json) on the spilling fake preloaded at 32,768, its first turn
    over half of 16,384 (Halo's own prompt): every turn is sent the cap the spill lowered (16,384), one load there,
    so "reloaded at 16k" is true; the reply's room is said once, sized by 16,384 (it was 32,768 on every turn). A
    helper call of the session (its compaction) leaves the session's cap as it is. The fourth turn (about 3,500
    tokens more) takes the session past 80 % of 16,384: its compaction's calls are sent 16,384 too (they were sent
    32,768, a reload onto the spilling window and back), the conversation cut to fit that window."""
    fake = _spilling_fake()
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 32768)
        turns = [_user("Reply with exactly one word: ready"),
                 _user("Context follows. " + "word " * int(4000 * 3.5 / 5) + "Reply with exactly one word: ready"),
                 _user("Reply with exactly one word: done"),
                 _user("More context. " + "token " * int(3500 * 3.5 / 6) + "Reply with exactly one word: fine")]
        rc, ended, out = _session_said(fh, fake, turns, timeout=400)
        ctx.check(f"a four-turn session: exit 0 and four turns ended, got {rc} {ended}", rc == 0 and ended == 4)
        chats = [r["body"] or {} for r in fake.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"]
        sent = [(b.get("options") or {}).get("num_ctx") for b in chats]
        cut = [ln.strip() for ln in out.splitlines() if "it summarises a transcript cut to fit" in ln]
        ctx.check(f"the session compacted within 16,384 and says so, got {cut} {out[-900:]!r}",
                  bool(cut) and all("window (16,384)" in ln for ln in cut))
        # four turns and, as the session grows past 80 % of 16,384, its compaction's calls: every one at 16,384
        ctx.check(f"every call is sent 16,384, got {sent}", len(sent) >= 4 and all(n == 16384 for n in sent))
        ctx.check(f"one load, at 16,384, got {fake.loads}", [x["num_ctx"] for x in fake.loads] == [16384])
        ctx.check(f"the line names 16k, got {out[-900:]!r}", "reloaded at 16k, the largest known to fit the card" in out)
        ctx.check(f"the reply's room is said once, sized by 16,384, got {out[-900:]!r}",
                  out.count("the reply's room is") == 1 and "sized by the 16,384 window" in out)
        ctx.check(f"no line names the 32,768 window as the one sized, got {out[-900:]!r}", "32,768 window" not in out)
        # 3.6.0.19 LM batch 2 (the coordinator's ruling): from the first request it sends, the tool block of a plain
        # session whose window is the cap, every request the same; every line names that one window
        names = _chat_tool_names(fake)
        ref = _plain_session_names(16384, ["Reply with exactly one word: ready"])[0]
        full = _plain_session_names(CAP, ["Reply with exactly one word: ready"])[0]
        print(f"  the cap's block {len(ref)} tools, the resolved window's {len(full)}; sent {[len(n) for n in names]}")
        ctx.check(f"the first request carries the cap's tool block ({len(ref)} tools), got {names[:1]}",
                  bool(names) and names[0] == ref)
        ctx.check(f"every later request carries the same names, got {[len(n) for n in names]}",
                  all(n == names[0] for n in names))
        ctx.check(f"the cap's block is not the resolved window's (the test sees a difference), {len(ref)} {len(full)}",
                  ref != full)
        diet = [ln.strip() for ln in out.splitlines() if "not offered to" in ln]
        ctx.check(f"the diet line names the window sent, got {diet}",
                  bool(diet) and all("(window 16,384)" in ln for ln in diet))
        ctx.check(f"no line names 65,536, got {[ln for ln in out.splitlines() if '65,536' in ln]}", "65,536" not in out)
    finally:
        fake.stop()


@test
def test_a_session_held_at_a_spill_cap_answered_exceeds_the_context_is_never_resent_past_its_cap(ctx: Ctx):
    """3.6.0.20 E7 (3.6.0.19 built the cap with no test of its own): a session of more turns held at the cap a spill
    lowered (16,384); before its second turn the server starts counting the prompt larger than Halo's estimate, and it
    answers a request past the window with the 400 "exceeds the available context size" (not a cut). The
    "prompt exceeds num_ctx" retry never re-sends past the cap: no load above 16,384, every request at or under it."""
    fake = _spilling_fake()
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 32768)
        fake.cut_shape = "reject"

        def count_more(_turn):
            fake.count_ratio = 1.6
        turns = [_user("Reply with exactly one word: ready"),
                 _user("Context follows. " + "word " * int(8000 * 3.5 / 5) + "Reply with exactly one word: ready")]
        rc, ended, out = _session_said(fh, fake, turns, timeout=400, between=count_more)
        sent = [(b.get("options") or {}).get("num_ctx") for b in _chats(fake)]
        said = [ln.replace("\x1b[2m", "").replace("\x1b[0m", "").strip() for ln in out.splitlines()
                if "↳" in ln or "rror" in ln]
        print(f"  rc {rc} ended {ended} sent {sent} rejects {fake.rejects} said {said[-3:]}")
        ctx.check(f"the server answered a request with the 400, got {fake.rejects}", bool(fake.rejects))
        ctx.check(f"no load above the cap, got {fake.loads}", all(x["num_ctx"] <= 16384 for x in fake.loads))
        ctx.check(f"every request at or under 16,384, got {sent}", bool(sent) and all(n <= 16384 for n in sent))
        ctx.check(f"both turns end, got {rc} {ended}", ended == 2)
    finally:
        fake.stop()


@test
def test_a_session_with_no_spill_is_sent_the_tool_block_of_its_window_every_turn(ctx: Ctx):
    """3.6.0.19 LM batch 2: a session of more turns on the plain fake (no spill): every request's tool names are those
    the product's own measure gives at the resolved window (the host's max_ctx), as before this batch: nothing is
    shaped again. The measure's registry is the built-in tools only: the session's own others (none of the measure's)
    are compared as the same in every request."""
    fake = L._fake()
    try:
        fh = L._home(fake)
        texts = ["Reply with exactly one word: ready", "Reply with exactly one word: done"]
        rc, ended, out = _session_said(fh, fake, [_user(t) for t in texts], timeout=300)
        ctx.check(f"a two-turn session: exit 0 and two turns ended, got {rc} {ended}", rc == 0 and ended == 2)
        sent = [(b.get("options") or {}).get("num_ctx") for b in L._turn_chats(fake)]
        ctx.check(f"every turn is sent the resolved window {CAP:,}, got {sent}", bool(sent) and set(sent) == {CAP})
        names = _chat_tool_names(fake)
        want = [_measured_names(fh, CAP, t) for t in texts]
        ctx.check(f"one request with tools per turn, got {len(names)}", len(names) == len(texts))
        for i, (got, w) in enumerate(zip(names, want)):
            own = [n for n in got if n in w]
            ctx.check(f"turn {i + 1}: the measure's block at {CAP:,} ({len(w)} tools), got {own}", own == w)
            ctx.check(f"turn {i + 1}: the session's other tools as on the first, got {got}",
                      [n for n in got if n not in w] == [n for n in names[0] if n not in want[0]])
    finally:
        fake.stop()


@test
def test_a_session_whose_resolved_window_moves_after_its_first_turn_keeps_its_first_tool_block(ctx: Ctx):
    """3.6.0.20 E3: the window a session resolves moves between turn 1 and turn 2 (here the host's max_ctx is lowered
    in the home's config; in real use the card's free memory falls) while the model stays loaded at the first window:
    turn 2 is sent the loaded window AND turn 1's tool names (it was: the block of the window resolved now)."""
    fake = L._fake()
    try:
        fh = L._home(fake)
        cfg = Path(fh["home"]) / ".halo" / "config.json"

        def lower(_turn):
            data = json.loads(cfg.read_text(encoding="utf-8"))
            data["ollama"]["hosts"][0]["max_ctx"] = 16384
            cfg.write_text(json.dumps(data), encoding="utf-8")
        texts = ["Reply with exactly one word: ready", "Reply with exactly one word: done"]
        rc, ended, _out = _session_said(fh, fake, [_user(t) for t in texts], timeout=300, between=lower)
        ctx.check(f"a two-turn session: exit 0 and two turns ended, got {rc} {ended}", rc == 0 and ended == 2)
        sent = [(b.get("options") or {}).get("num_ctx") for b in L._turn_chats(fake)]
        ctx.check(f"both turns are sent the loaded {CAP:,}, got {sent}", bool(sent) and set(sent) == {CAP})
        names = _chat_tool_names(fake)
        ctx.check(f"two requests with tools, the same names, got {[len(n) for n in names]}",
                  len(names) == 2 and names[0] == names[1])
        small = _measured_names(fh, 16384, texts[1])
        ctx.check(f"the test sees a difference: the block at 16,384 is smaller ({len(small)} tools)",
                  len([n for n in names[0] if n in small]) == len(small) and len(small) < len(names[0]))
    finally:
        fake.stop()


@test
def test_a_first_call_whose_block_raises_the_window_again_and_again_is_shaped_for_the_window_sent(ctx: Ctx):
    """3.6.0.20 E6: a session's first call whose tool block, shaped for each window, needs the next power of two four
    times (8,192 -> 131,072, the ceiling): the rounds run until the window sent stops rising, so the request is shaped
    for the window it is sent (it was three rounds: shaped for 65,536, sent at 131,072). In process: the session's
    shaper, start_window and the decision are stand-ins (restored after); first_block and prepare_window are the
    product's."""
    import tempfile as _tf
    from types import SimpleNamespace as NS
    import halo_harness.agent.loop as loop_mod
    import halo_harness.agent.ollama_window_truth as truth_mod
    import halo_harness.agent.prompt_wire as wire_mod
    import halo_harness.agent.reply_room as room_mod
    import halo_harness.providers.ollama_hw as hw_mod
    from halo_harness.agent.ollama_window import _state
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    from tests.helpers.mock_ollama import MockUpstream
    from tests.test_ollama_calibrate import _minimal_session
    mock = MockUpstream().start()
    session = _minimal_session(_tf.mkdtemp(prefix="e6-rounds-"), mock)
    session.many_turns = True
    shaped: list = []

    def tools_for(w):  # a block of about 1.2 x the window it is shaped for
        return [{"name": "Big", "description": "word " * int(w * 1.2 * 3.5 / 5),
                 "input_schema": {"type": "object", "properties": {}}}]

    def shaper(_session, ref, request, **_kw):
        def reshape(window=None):
            w = window or getattr(session, "_shape_window", None) or reshape.before
            shaped.append(w)
            return request[0], request[1], tools_for(w)
        reshape.before = 8192
        return reshape

    def start(_session, *, host, ref, cap, cap_source, **_kw):
        _state(session)["first_call"] = (host.url, ref.model)
        return 8192, "fit estimate", False
    decision = NS(num_ctx=8192, source="fit estimate", trained_context=131072, fit_estimate=None, learned_cap=None,
                  remote=False, recorded_does_not_fit=False, cpu_only=False, profile=None, gpu_layers=None,
                  gpu_fits_up_to=None, supports_thinking=False, host_max_ctx=None, offloaded=None,
                  fit_source="fit estimate", tools_max=99)
    saved = (loop_mod.resolve_ollama_host, wire_mod.one_shot_shaper, truth_mod.start_window, room_mod.for_call,
             hw_mod.resolve_context_decision)
    loop_mod.resolve_ollama_host = lambda name, env: OllamaHost(name="gpu-box", url=mock.base_url)
    wire_mod.one_shot_shaper, truth_mod.start_window = shaper, start
    room_mod.for_call = lambda _s, _ref, window, requested, *_a, **_k: (requested, window)
    hw_mod.resolve_context_decision = lambda *_a, **_k: decision
    try:
        ref = parse_model_ref("ol:plain-text")
        session.model_ref = ref
        route = Route(provider="ollama", upstream_model="plain-text", dialect="ollama")
        body = session._build_ollama_body_for_ref(
            ref=ref, route=route, profile=resolve_profile(route), system_text="sys",
            messages=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}], tools=tools_for(8192),
            tool_choice=None, effort=None, requested_max_tokens=256)
        sent = (body.get("options") or {}).get("num_ctx")
        ctx.check(f"the windows it was shaped for rise to the ceiling, got {shaped}", 131072 in shaped)
        ctx.check(f"sent at 131,072, got {sent}", sent == 131072)
        desc = ((body.get("tools") or [{}])[0].get("function") or {}).get("description", "")
        ctx.check(f"the block sent is the one shaped for the window sent ({sent}), got the block of "
                  f"{[w for w in shaped if tools_for(w)[0]['description'] == desc]}",
                  desc == tools_for(sent or 0)[0]["description"])
    finally:
        (loop_mod.resolve_ollama_host, wire_mod.one_shot_shaper, truth_mod.start_window, room_mod.for_call,
         hw_mod.resolve_context_decision) = saved
        mock.stop()


# ---- 3.6.0.19 LM batch 3: a new session on a model Halo never measured -------------------------------------------

def _unmeasured_fake(trained: int = 202752, spill: bool = False):
    """A model Halo has never measured: its `/api/show` names no `num_ctx`, its `model_info` an architecture Halo's
    memory estimate does not know (no estimate), the home has no `ollama-fit.json` and the host no `max_ctx` (the
    home `_unmeasured_home` makes): the window it resolves is a default the prompt floor raises over. `spill`: a
    window of 32,768 or more runs half on the CPU."""
    fake = _spilling_fake() if spill else L._fake()
    fake.show_responses[MODEL]["model_info"] = {
        "general.architecture": "examplearch", "examplearch.context_length": trained,
        "examplearch.embedding_length": 2048, "examplearch.block_count": 47}
    return fake


def _unmeasured_home(fake):
    return L._home(fake, max_ctx=None)


def _chats(fake) -> list:
    return [r["body"] or {} for r in fake.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"]


def _carries(body: dict, text: str) -> bool:
    return any(text in json.dumps(m.get("content"), ensure_ascii=False) for m in body.get("messages") or []
               if isinstance(m, dict) and m.get("role") == "user")


def _windows_named(out: str) -> dict:
    """Every window a `↳` line names: the diet line's `(window N)`, "sized by the N window", "reloaded at Nk"."""
    import re
    return {"diet": {int(w.replace(",", "")) for ln in out.splitlines() if "not offered to" in ln
                     for w in re.findall(r"\(window ([\d,]+)\)", ln)},
            "sized": {int(w.replace(",", "")) for w in re.findall(r"sized by the ([\d,]+) window", out)},
            "reloaded": set(re.findall(r"reloaded at (\d+k)", out))}


FIRST = "Question one: what is a harness? Reply with exactly one word: ready"


@test
def test_a_new_session_on_a_model_never_measured_names_the_one_window_it_is_sent(ctx: Ctx):
    """3.6.0.19 LM batch 3: a session of three turns on a model Halo never measured, nothing loaded: the window it
    resolves (a default) is raised over by the first request; the tool block is the one of the window that first call
    is sent, the diet line names that window and no other, nothing is compacted, every request holds the person's
    first message (it was: the block of the default and a diet line naming the default, a window never sent)."""
    fake = _unmeasured_fake()
    try:
        fh = _unmeasured_home(fake)
        texts = [FIRST, "Question two: reply with exactly one word: done", "Question three: what did I ask first?"]
        rc, ended, out = _session_said(fh, fake, [_user(t) for t in texts], timeout=400)
        ctx.check(f"a three-turn session: exit 0 and three turns ended, got {rc} {ended}", rc == 0 and ended == 3)
        chats = _chats(fake)
        sent = [(b.get("options") or {}).get("num_ctx") for b in chats]
        ctx.check(f"three calls, no compaction call (each carries the first question), got {len(chats)} "
                  f"{[_carries(b, 'Question one') for b in chats]}",
                  len(chats) == 3 and all(_carries(b, "Question one") for b in chats))
        ctx.check(f"every window sent holds its request (nothing cut), got {fake.cuts}", not fake.cuts)
        named = _windows_named(out)
        ctx.check(f"the diet line names exactly one window, the first sent ({sent[:1]}), got {named['diet']}",
                  bool(sent) and named["diet"] == {sent[0]})
        ctx.check(f"every window a line names is sent, got {named} {sent}",
                  named["sized"] <= set(sent) and not named["reloaded"])
        ctx.check(f"no line says the request will be cut, got {out[-900:]!r}", "this will be cut" not in out)
        ctx.check("the third request still carries the first user message",
                  len(chats) == 3 and _carries(chats[2], "Question one"))
        names = _chat_tool_names(fake)
        ctx.check(f"one tool block on every request, got {[len(n) for n in names]}",
                  bool(names) and all(n == names[0] for n in names))
    finally:
        fake.stop()


@test
def test_a_session_held_at_a_larger_loaded_window_is_sent_that_windows_tool_block(ctx: Ctx):
    """3.6.0.19 LM batch 3: another program left the model loaded at 65,536, wholly on the card; the session holds that
    window (nothing reloaded) and is sent the tool block of a plain session at 65,536 from its first request on (it
    was the block of the window the home resolves, a diet line naming that window)."""
    fake = _unmeasured_fake()
    try:
        fh = _unmeasured_home(fake)
        fake.preload(MODEL, CAP)
        texts = [FIRST, "Question two: reply with exactly one word: done"]
        rc, ended, out = _session_said(fh, fake, [_user(t) for t in texts], timeout=400)
        ctx.check(f"a two-turn session: exit 0 and two turns ended, got {rc} {ended}", rc == 0 and ended == 2)
        sent = [(b.get("options") or {}).get("num_ctx") for b in _chats(fake)]
        ctx.check(f"every call holds the loaded window, nothing reloaded, got {sent} {fake.loads}",
                  bool(sent) and set(sent) == {CAP} and not fake.loads)
        names = _chat_tool_names(fake)
        ref = _plain_session_names(CAP, [FIRST])[0]
        ctx.check(f"the first request carries a plain session's block at {CAP:,} ({len(ref)} tools), got "
                  f"{[len(n) for n in names[:1]]}", bool(names) and names[0] == ref)
        ctx.check(f"every later request the same names, got {[len(n) for n in names]}",
                  all(n == names[0] for n in names))
        named = _windows_named(out)
        ctx.check(f"a diet line names only the window held, got {named['diet']}", named["diet"] <= {CAP})
    finally:
        fake.stop()


@test
def test_a_session_on_a_spilling_load_with_nothing_measured_names_no_window_it_does_not_send(ctx: Ctx):
    """3.6.0.19 LM batch 3: the model loaded at 65,536, a window that runs half on the CPU, and nothing measured: the
    reload goes to the window the request needs; no line names a window that is not sent, none says a window nothing
    measured is "known to fit the card", and the tool block is one on every request."""
    fake = _unmeasured_fake(spill=True)
    try:
        fh = _unmeasured_home(fake)
        fake.preload(MODEL, CAP)
        texts = [FIRST, "Question two: reply with exactly one word: done", "Question three: what did I ask first?"]
        rc, ended, out = _session_said(fh, fake, [_user(t) for t in texts], timeout=400)
        ctx.check(f"a three-turn session: exit 0 and three turns ended, got {rc} {ended}", rc == 0 and ended == 3)
        sent = [(b.get("options") or {}).get("num_ctx") for b in _chats(fake)]
        ctx.check(f"reloaded under the spill once, every call there, got {sent} {fake.loads}",
                  bool(sent) and len(set(sent)) == 1 and sent[0] < 32768 and len(fake.loads) == 1)
        from halo_harness.providers.ollama_prompt import fmt_window
        named = _windows_named(out)
        ctx.check(f"every window a line names is sent, got {named} {sent}",
                  named["diet"] <= set(sent) and named["sized"] <= set(sent)
                  and named["reloaded"] <= {fmt_window(s) for s in sent})
        ctx.check(f"no line says a window nothing measured is known to fit, got {out[-900:]!r}",
                  "known to fit the card" not in out)
        names = _chat_tool_names(fake)
        ctx.check(f"one tool block on every request, got {[len(n) for n in names]}",
                  bool(names) and all(n == names[0] for n in names))
    finally:
        fake.stop()


@test
def test_a_first_request_larger_than_the_window_is_never_compacted(ctx: Ctx):
    """3.6.0.19 LM batch 3: a model whose trained window (4,096) is smaller than Halo's own first request: a
    conversation with no earlier turn has nothing to summarise, so it is not compacted (it was: "this will be cut:
    compacting first", a compaction that lost the question). The person reads the existing line that the system prompt,
    the memory and the tools alone are more than the window holds, and the request is sent as "send anyway" sends it."""
    fake = _unmeasured_fake(trained=4096)
    try:
        fh = _unmeasured_home(fake)
        rc, ended, out = _session_said(fh, fake, [_user(FIRST)], timeout=400)
        ctx.check(f"one turn: exit 0 and it ended, got {rc} {ended}", rc == 0 and ended == 1)
        chats = _chats(fake)
        ctx.check(f"no compaction call: one call, carrying the first question, got {len(chats)} "
                  f"{[_carries(b, 'Question one') for b in chats]}",
                  len(chats) == 1 and _carries(chats[0], "Question one"))
        ctx.check(f"no line says it compacts or summarises, got {out[-900:]!r}",
                  "compact" not in out and "summarises" not in out)
        ctx.check(f"the line that the fixed part alone is over the window, got {out[-900:]!r}",
                  "the system prompt, the memory and the tools alone are" in out and "this 4,096 window" in out)
        ctx.check(f"sent as 'send anyway' sends it, got {out[-900:]!r}", "sending anyway (the tail is kept)" in out)
    finally:
        fake.stop()


@test
def test_a_first_request_over_a_max_ctx_window_names_the_max_ctx(ctx: Ctx):
    """3.6.0.20 E5: the host's max_ctx (4,096) holds the window below Halo's own first request: the line says that, not
    "a bigger-window model" (the trained window, the test above, keeps those words)."""
    fake = _unmeasured_fake()
    try:
        fh = L._home(fake, max_ctx=4096)
        rc, ended, out = _session_said(fh, fake, [_user(FIRST)], timeout=400)
        ctx.check(f"one turn: exit 0 and it ended, got {rc} {ended}", rc == 0 and ended == 1)
        line = next((ln.replace("\x1b[2m", "").replace("\x1b[0m", "").strip() for ln in out.splitlines()
                     if "alone are" in ln), "")
        ctx.check(f"the line names the max_ctx, got {line!r}",
                  "this 4,096 window holds" in line and line.endswith(": the host's max_ctx sets that window"))
    finally:
        fake.stop()


@test
def test_a_first_request_sent_anyway_whose_reply_fills_the_window_is_not_compacted_after_it(ctx: Ctx):
    """3.6.0.19 (its review): the first request is sent anyway (the test above); the reply then uses its whole room and
    ends at the window (done_reason "length"). Before: "cut the reply at the window: compacted and re-sent", a
    compaction of a conversation with no earlier answer, the ladder of rungs, exit 1 (five calls). Now the cut reply
    stands as the answer: one call, exit 0, nothing compacted."""
    for shape in (None, "edge"):
        fake = _unmeasured_fake(trained=4096)
        fake.reply_tokens = 100000
        fake.cut_shape = shape
        try:
            fh = _unmeasured_home(fake)
            rc, ended, out = _session_said(fh, fake, [_user(FIRST)], timeout=400)
            chats = _chats(fake)
            ctx.check(f"cut shape {shape}: one turn, exit 0, got {rc} {ended}", rc == 0 and ended == 1)
            ctx.check(f"cut shape {shape}: one call, carrying the first question, got {len(chats)} "
                      f"{[_carries(b, 'Question one') for b in chats]}",
                      len(chats) == 1 and _carries(chats[0], "Question one"))
            ctx.check(f"cut shape {shape}: no line says it compacts or summarises, got {out[-900:]!r}",
                      "compact" not in out and "summarises" not in out)
        finally:
            fake.stop()


@test
def test_a_first_request_judged_to_fit_then_cut_by_the_server_stands_with_one_true_line(ctx: Ctx):
    """3.6.0.20 E8: a first request the pre-send check judged to fit (so nothing announced "sending anyway"), at a
    window that cannot grow (the host's max_ctx 16,384): (a) the server counts it larger and cuts it to half the window;
    (b) its reply runs to the window's end. Neither is compacted (a conversation with no earlier answer has nothing to
    summarise; it was: "compacted and re-sent"); the answer stands and one line says so."""
    cases = (("trimmed", 1.6, 2, "half", "gpu-box read 8.2k of "),  # half the window + 2, trim_line's format
             ("cut reply", 1.3, 100000, None, "gpu-box cut the reply at the window ("))  # read whole, less room
    for name, ratio, reply, shape, head in cases:
        fake = L._fake()
        try:
            fh = L._home(fake, max_ctx=16384)
            fake.count_ratio, fake.reply_tokens, fake.cut_shape = ratio, reply, shape
            text = "Context follows. " + "word " * int(6000 * 3.5 / 5) + FIRST
            rc, ended, out = _session_said(fh, fake, [_user(text)], timeout=400)
            print(f"  {name}: cuts {fake.cuts} sent {[(b.get('options') or {}).get('num_ctx') for b in _chats(fake)]}")
            chats = _chats(fake)
            ctx.check(f"{name}: one turn, exit 0, one call, got {rc} {ended} {len(chats)}",
                      rc == 0 and ended == 1 and len(chats) == 1)
            ctx.check(f"{name}: no line says it compacts or summarises, got {out[-700:]!r}",
                      "compact" not in out.replace("nothing earlier to compact", "") and "summarises" not in out)
            said = [ln.replace("\x1b[2m", "").replace("\x1b[0m", "").strip()[2:] for ln in out.splitlines()
                    if "nothing earlier to compact" in ln]
            tail = ("of the first request (its window is 16k): nothing earlier to compact, the answer stands"
                    if shape else "16k tokens): nothing earlier to compact, the reply stands as it is")
            ctx.check(f"{name}: one line, word for word, got {said}",
                      len(said) == 1 and said[0].startswith(head) and said[0].endswith(tail))
            ctx.check(f"{name}: no 'sending anyway' line (the check judged it to fit), got {out[-700:]!r}",
                      "sending anyway" not in out)
        finally:
            fake.stop()


@test
def test_a_one_shot_too_large_for_the_spill_window_is_sent_the_larger_one_and_says_so(ctx: Ctx):
    # 3.6.0.12 OS: a prompt of about 12,000 tokens does not fit 16,384 with the reply's room: the larger window is
    # sent, and no line claims a reload at 16k
    prompt = _padded(12000)
    fake = _spilling_fake()
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 32768)
        result = _ask(fh, fake, prompt, "--verbose")
        _ok(ctx, result, "a one-shot of about 12,000 tokens")
        sent = [o.get("num_ctx") for o in _opts(fake)]
        ctx.check(f"the larger window is sent, got {sent}", bool(sent) and sent[0] > 16384)
        out = result.stdout
        ctx.check(f"no line claims 16k, got {out[-600:]!r}", "reloaded at 16k" not in out)
        ctx.check(f"the line says the larger window is kept and why, got {out[-600:]!r}",
                  "partly on the CPU" in out and "the request does not fit 16k" in out)
    finally:
        fake.stop()


# ---- S2: a failed /api/ps read is unknown --------------------------------------------------------------------------

def _break_ps(fake) -> None:
    def broken():
        raise RuntimeError("ps down")
    fake.ps_snapshot = broken


@test
def test_an_unreadable_ps_claims_no_load_and_stores_nothing(ctx: Ctx):
    fake = L._fake()
    _break_ps(fake)
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 131072)  # another client's window
        result = L._run(fh, fake, "hi", "--output-format", "stream-json", "--verbose")
        _ok(ctx, result, "an unreadable /api/ps")
        status = [ln for ln in result.stdout.splitlines() if '"subtype": "status"' in ln and "loading" in ln]
        ctx.check(f"no 'loading' line on an unknown reading, got {status}", not status)
        ctx.check(f"nothing stored as the window truth, got {_fit(fh).get('window_truth')}",
                  not _fit(fh).get("window_truth"))
    finally:
        fake.stop()


@test
def test_an_unreadable_ps_keeps_the_window_last_used_and_reloads_nothing(ctx: Ctx):
    fake = L._fake()
    try:
        fh = L._home(fake)
        _ok(ctx, _ask(fh, fake, _padded(20000)), "a large first run")  # loads at a large window
        first = fake.loads[-1]["num_ctx"] if fake.loads else None
        _break_ps(fake)
        before = len(fake.loads)
        _ok(ctx, L._run(fh, fake), "a small run with /api/ps unreadable")
        ctx.check(f"no reload on an unknown reading, got {fake.loads[before:]}", len(fake.loads) == before)
        sent = _opts(fake)
        ctx.check(f"the window last used ({first}) is kept, got {sent[-1].get('num_ctx') if sent else None}",
                  bool(sent) and sent[-1].get("num_ctx") == first)
    finally:
        fake.stop()


# ---- S3: the ratio takes no shortened count ------------------------------------------------------------------------

@test
def test_the_token_ratio_takes_no_count_a_cached_prefix_may_have_shortened(ctx: Ctx):
    from halo_harness.agent import ollama_window_truth as W
    d = Path(tempfile.mkdtemp())
    url, model = "http://gpu-box:11434", "m:1b"
    for raw, seen in [(6000, 6000), (9000, 5000), (11000, 6000), (13000, 7500), (15000, 8500)]:
        W.record_ratio(d, url, model, raw_prompt=raw, prompt_eval_count=seen)
    ctx.check(f"the judge's sequence leaves the ratio at 1.0, got {W.token_ratio(d, url, model)}",
              W.token_ratio(d, url, model) == 1.0)
    W.record_ratio(d, url, model, raw_prompt=10000, prompt_eval_count=7000, fresh=True)
    W.record_ratio(d, url, model, raw_prompt=10000, prompt_eval_count=7000, fresh=True)
    stored = W._section(d, "token_ratio", W._key(url, model)).get("ratio")
    ctx.check(f"a call that loaded the model (nothing cached) is a measurement, got {stored}",
              isinstance(stored, float) and stored < 0.95)


# ---- S10: one read per turn, bounded -------------------------------------------------------------------------------

class _SlowPs(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        time.sleep(5)
        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"models": []}')
        except OSError:
            pass


@test
def test_the_read_after_a_turn_waits_at_most_a_second(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.agent import ollama_window_truth as W
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SlowPs)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        host = SimpleNamespace(url=f"http://127.0.0.1:{srv.server_address[1]}", name="gpu-box", api_key=None,
                               max_ctx=None, keep_alive=None)
        session = SimpleNamespace(state_dir=Path(tempfile.mkdtemp()), model_ref=None,
                                  _ollama_turn_reads={(host.url, MODEL): {"host": host, "model": MODEL,
                                                                          "num_ctx": 16384, "num_gpu": None}})
        t0 = time.monotonic()
        W.turn_end_check(session)
        took = time.monotonic() - t0
        ctx.check(f"a server that stops answering adds at most about a second, took {took:.2f} s", took < 1.6)
        ctx.check("the reads are spent", not session._ollama_turn_reads)
    finally:
        srv.shutdown()


@test
def test_after_call_reads_nothing_and_turn_end_check_reads_ps_once_per_turn(ctx: Ctx):
    from types import SimpleNamespace
    import halo_harness.providers.ollama as O
    from halo_harness.agent import ollama_window_truth as W
    host = SimpleNamespace(url="http://gpu-box:11434", name="gpu-box", api_key=None, max_ctx=None, keep_alive=None)
    reads = []

    def fake_ps(h, timeout=None):
        reads.append((h.url, timeout))
        return {"models": [{"model": MODEL, "name": MODEL, "context_length": 16384, "size": 2 * GB,
                            "size_vram": 2 * GB, "digest": "sha256:1"}]}
    real_ps, real_host = O.fetch_ps, W._host_for_url
    O.fetch_ps, W._host_for_url = fake_ps, (lambda session, url: host)
    try:
        session = SimpleNamespace(state_dir=Path(tempfile.mkdtemp()), model_ref=SimpleNamespace(model=MODEL),
                                  _ollama_window_state={"factor": {}, "trim_turn": None, "last": None})
        req = SimpleNamespace(prebuilt_ollama_body={"model": MODEL, "options": {"num_ctx": 16384}},
                              creds=SimpleNamespace(base_url=host.url))
        meta = {"timing_ns": {"prompt_eval_count": 5000, "eval_count": 2}}
        for _ in range(3):  # three calls of one turn (a tool loop)
            W.after_call(session, req, meta)
        ctx.check(f"no /api/ps read after each call, got {reads}", not reads)
        W.turn_end_check(session)
        ctx.check(f"one read at the end of the turn, bounded to a second, got {reads}",
                  len(reads) == 1 and reads[0][1] is not None and reads[0][1] <= 1.0)
        got = W.truth(session.state_dir, host.url, MODEL)
        ctx.check(f"and what it read is the window truth, got {got}", got.get("fits") == 16384)
    finally:
        O.fetch_ps, W._host_for_url = real_ps, real_host


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
