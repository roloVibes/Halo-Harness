"""scripts/realcheck/fakes.py -- what the steps talk to instead of the world, all on 127.0.0.1 and in this process.

`Provider` is the test suite's own fake OpenAI-dialect upstream (tests/helpers/mock_openai.MockUpstream), reached by
Halo through `BRIDGE_OPENROUTER_BASE_URL` with any `or:` model, answering by what the request says (the markers below),
never by model name, so a sub-agent or a workflow step on another model is answered too:

  RC-ASK                 a one-line answer, ANSWER
  RC-WORK file=P wf=W    a real turn: Read P, then an Agent spawn (RC-SUB), then Workflow W (RC-SUB), then WORK_DONE
  RC-PACK agent=A        an Agent spawn to the agent named A (RC-SUB), then PACK_DONE
  RC-HANG                an Agent spawn whose sub-agent's model call never answers until `release()` (mid-run)
  RC-SLOW                the main model call itself never answers until `release()`
  RC-BASH                a Bash call `SHELL_HOLD` (a job in the background and one in front: the turn holds in the shell)
  RC-BGBASH              a Bash call `SHELL_BACKGROUND` with run_in_background, then ANSWER (the job outlives the turn)
  RC-SUB / anything else  SUB_DONE / ANSWER

Every request is kept (`requests`, with its size in bytes). `Ollama` is tests/helpers/mock_ollama_loads.
LoadCountingOllama (its load / unload counters are what step 8 reads). `browser_command(root)` makes the program a
person's browser would be (BROWSER): it writes each URL it is asked to open to a file and exits 0."""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import threading
import time
from pathlib import Path

ANSWER, SUB_DONE, WORK_DONE, PACK_DONE = "RC-ANSWER-42", "RC-SUB-DONE", "RC-WORK-DONE", "RC-PACK-DONE"
SHELL_HOLD, SHELL_BACKGROUND = "sleep 6011 & sleep 6011", "sleep 6012"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(str(p.get("text") or "") for p in content or [] if isinstance(p, dict))


def _last_user(body: dict) -> str:
    for m in reversed((body or {}).get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return _text(m.get("content"))
    return ""


def text_step(text: str) -> list:
    """One streamed assistant message (the chunks tests/helpers/session_rig.text_step makes)."""
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def tool_step(*calls) -> list:
    """One assistant message calling tools: `calls` = (name, arguments, call id)."""
    tcs = [{"index": i, "id": cid, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
           for i, (n, a, cid) in enumerate(calls)]
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": tcs}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def _tool_results(body: dict) -> int:
    return sum(1 for m in (body or {}).get("messages") or [] if isinstance(m, dict) and m.get("role") == "tool")


class Provider:
    def __init__(self) -> None:
        from tests.helpers.mock_openai import SCENARIOS, MockUpstream
        self._scenarios = SCENARIOS
        self.mock = MockUpstream()
        self.mock.models_response = {"data": [{"id": "mock/realcheck", "name": "realcheck",
                                               "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"},
                                               "supported_parameters": ["tools"]}]}
        self.gate = threading.Event()
        self.hung: list = []  # the markers of calls held at the gate
        self._lock = threading.Lock()
        self.calls: list = []  # (marker, size) per POST

    _KEYS = ("realcheck", "model")
    _MISSING = object()

    def start(self) -> "Provider":
        # the mock's scenario table is one dict for the whole process: what these names held before is put back on
        # stop (popping "model" took the mock's own default answer from every later test in the same process)
        self._saved = {k: self._scenarios.get(k, self._MISSING) for k in self._KEYS}
        self._scenarios["realcheck"] = self._answer
        self._scenarios["model"] = self._answer  # any model name that is not mock/<x>
        self.mock.start()
        return self

    @property
    def base_url(self) -> str:
        return self.mock.base_url

    def release(self) -> None:
        self.gate.set()

    def rearm(self) -> None:
        self.gate = threading.Event()
        with self._lock:
            self.hung.clear()

    def requests_with(self, marker: str) -> list:
        """The model calls whose user messages say `marker` (the text as typed: no JSON escaping)."""
        out = []
        for r in self.mock.requests:
            msgs = (r.get("body") or {}).get("messages") or [] if r.get("method") == "POST" else []
            if any(isinstance(m, dict) and m.get("role") == "user" and marker in _text(m.get("content")) for m in msgs):
                out.append(r)
        return out

    def size_of(self, req: dict) -> int:
        return len(json.dumps(req.get("body") or {}, ensure_ascii=False).encode("utf-8"))

    def _hold(self, marker: str) -> None:
        with self._lock:
            self.hung.append(marker)
        self.gate.wait(180)

    def _answer(self, h, body) -> None:
        try:
            self._script(h, body)
        except OSError:  # the caller went away (a launch this step killed while its call was held): nothing to say
            pass

    def _script(self, h, body) -> None:
        from tests.helpers.mock_openai import _finish
        last, done = _last_user(body), _tool_results(body)
        with self._lock:
            self.calls.append((last[:40], len(json.dumps(body or {}))))
        if "RC-SUBHANG" in last:
            self._hold("RC-SUBHANG")
            return _finish(h, text_step(SUB_DONE))
        if "RC-SUB" in last:
            return _finish(h, text_step(SUB_DONE))
        if "RC-SLOW" in last:
            self._hold("RC-SLOW")
            return _finish(h, text_step(ANSWER))
        for marker, args in (("RC-BGBASH", {"command": SHELL_BACKGROUND, "run_in_background": True}),
                             ("RC-BASH", {"command": SHELL_HOLD})):
            if marker in last:
                if done == 0:
                    return _finish(h, tool_step(("Bash", dict(args, description="rc shell"), "call_rc_shell")))
                return _finish(h, text_step(ANSWER))
        if "RC-HANG" in last:
            if done == 0:
                return _finish(h, tool_step(("Agent", {"description": "rc hang", "prompt": "RC-SUBHANG: wait",
                                                       "subagent_type": "general-purpose"}, "call_rc_hang")))
            return _finish(h, text_step(ANSWER))
        m = re.search(r"RC-PACK agent=(\S+)", last)
        if m:
            if done == 0:
                return _finish(h, tool_step(("Agent", {"description": "rc pack", "subagent_type": m.group(1),
                                                       "prompt": "RC-SUB: review README.md in one line"}, "call_rc_pack")))
            return _finish(h, text_step(PACK_DONE))
        m = re.search(r"RC-WORK file=(\S+) wf=(\S+)", last)
        if m:
            steps = [("Read", {"file_path": m.group(1)}, "call_rc_read"),
                     ("Agent", {"description": "rc sub", "prompt": "RC-SUB: answer in one line",
                                "subagent_type": "general-purpose"}, "call_rc_agent"),
                     ("Workflow", {"name": m.group(2), "task": "RC-SUB: answer in one line"}, "call_rc_wf")]
            if done < len(steps):
                return _finish(h, tool_step(steps[done]))
            return _finish(h, text_step(WORK_DONE))
        return _finish(h, text_step(ANSWER))

    def stop(self) -> None:
        self.release()
        saved, self._saved = getattr(self, "_saved", {}), {}
        for k in self._KEYS:
            if self._scenarios.get(k) != self._answer:  # another owner took the name since: theirs now
                continue
            was = saved.get(k, self._MISSING)
            if was is self._MISSING:
                self._scenarios.pop(k, None)
            else:
                self._scenarios[k] = was
        try:
            self.mock.stop()
        except Exception:
            pass


def ollama(models: dict):
    """A load-counting fake Ollama on loopback (tests/helpers/mock_ollama_loads.py), started."""
    from tests.helpers.mock_ollama_loads import LoadCountingOllama
    return LoadCountingOllama(models).start()


BROWSER_SCRIPT = """import sys, time
with open({out!r}, "a", encoding="utf-8") as f:
    f.write(repr(time.time()) + " " + " ".join(sys.argv[1:]) + "\\n")
"""


def browser_command(root: Path) -> "tuple[str, Path]":
    """(the BROWSER value, the file the opened URLs land in). A person's browser opens the page; this one writes the
    URL down and exits 0, so Halo knows a browser took it. Windows: an .exe launcher made by distlib (pip's own), since
    a .cmd would split the URL at its '&'."""
    root = Path(root)
    out = root / "browser-opened.txt"
    script = root / "realcheck-browser.py"
    body = BROWSER_SCRIPT.format(out=str(out))
    if sys.platform != "win32":
        script.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return str(script), out
    from pip._vendor.distlib.scripts import ScriptMaker
    script.write_text("#!python\n" + body, encoding="utf-8")  # distlib puts this Python in the launcher's shebang
    maker =ScriptMaker(str(root), str(root / "bin"), add_launchers=True)
    maker.executable = sys.executable
    made = maker.make(script.name)
    exe = next((p for p in made if p.endswith(".exe")), "")
    if not exe:
        raise RuntimeError(f"no browser launcher made: {made}")
    return exe, out


def opened_urls(out: Path) -> list:
    try:
        return [line.split(" ", 1)[1].strip() for line in out.read_text(encoding="utf-8").splitlines() if " " in line]
    except OSError:
        return []


def wait_opened(out: Path, timeout: float) -> str:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = opened_urls(out)
        if got:
            return got[-1]
        time.sleep(0.05)
    return ""


def free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def env_without(names_prefixes) -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith(tuple(names_prefixes))}
