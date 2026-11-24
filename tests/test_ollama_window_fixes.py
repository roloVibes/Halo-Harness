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


def _session_said(fh, fake, turns: list, timeout: float = 300) -> "tuple[int, int, str]":
    """`_session`'s client with `--output-format text --verbose`, so the `↳` lines a person reads are printed: each
    user line after the previous turn's end line (`◼ ...`). Returns (exit code, turns ended, everything printed)."""
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


@test
def test_a_session_under_the_spill_is_sent_the_window_the_line_names_every_turn(ctx: Ctx):
    """3.6.0.19 LM: a session of more turns (stream-json) on the spilling fake preloaded at 32,768, its first turn
    over half of 16,384 (Halo's own prompt): every turn is sent the cap the spill lowered (16,384), one load there,
    so "reloaded at 16k" is true; the reply's room is said once, sized by 16,384 (it was 32,768 on every turn). A
    helper call of the session (its compaction) leaves the session's cap as it is."""
    fake = _spilling_fake()
    try:
        fh = L._home(fake)
        fake.preload(MODEL, 32768)
        turns = [_user("Reply with exactly one word: ready"),
                 _user("Context follows. " + "word " * int(4000 * 3.5 / 5) + "Reply with exactly one word: ready"),
                 _user("Reply with exactly one word: done")]
        rc, ended, out = _session_said(fh, fake, turns)
        ctx.check(f"a three-turn session: exit 0 and three turns ended, got {rc} {ended}", rc == 0 and ended == 3)
        sent = [o.get("num_ctx") for o in _opts(fake)]
        # three turns (and, as the session grows past 80 % of 16,384, its compaction's calls): every one at 16,384
        ctx.check(f"every call is sent 16,384, got {sent}", len(sent) >= 3 and all(n == 16384 for n in sent))
        ctx.check(f"one load, at 16,384, got {fake.loads}", [x["num_ctx"] for x in fake.loads] == [16384])
        ctx.check(f"the line names 16k, got {out[-900:]!r}", "reloaded at 16k, the largest known to fit the card" in out)
        ctx.check(f"the reply's room is said once, sized by 16,384, got {out[-900:]!r}",
                  out.count("the reply's room is") == 1 and "sized by the 16,384 window" in out)
        ctx.check(f"no line names the 32,768 window as the one sized, got {out[-900:]!r}", "32,768 window" not in out)
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
