"""tests.helpers.prompt_budget_rig -- Halo 3.3.5.0 R4: the loop rig
(tests/helpers/model_switch_rig.py: a real Session over a fake Ollama on
127.0.0.1:0, a fake home with its own MEMORY.md and topic files) with three
more models for the prompt budget's tests:

    tight:14b   trained 32,768; completion, tools   (the "32k fake")
    wide:14b    trained 131,072; completion, tools  (the bigger-window model)
    tiny:3b     trained 12,288; completion, tools

`answer(prompt_eval=..., load_ns=...)` makes a scenario that answers "ok" with
a scripted count or load time; `fill_to(session, tokens)` pads the history to
about that many tokens. Never a real Ollama or a model call, never the real
~/.halo, never the real memory directory (build_fake_home seeds its own).
"""

from __future__ import annotations

import json
import queue
import threading

from tests.helpers import model_switch_rig as M
from tests.helpers.mock_ollama import _finish_chat

EXTRA = {"tight:14b": (32768, ["completion", "tools"]), "wide:14b": (131072, ["completion", "tools"]),
         "tiny:3b": (12288, ["completion", "tools"])}


def answer(prompt_eval="real", load_ns: int = 100_000, text: str = "ok"):
    def _scn(handler, body):
        if M.COMPACTION_MARKER in json.dumps((body or {}).get("messages") or []):
            text_out = M.summary_text()
        else:
            text_out = text
        count = prompt_eval(body) if callable(prompt_eval) else prompt_eval
        _finish_chat(handler, [{"message": {"role": "assistant", "content": text_out}, "done": True, "done_reason": "stop",
                                "prompt_eval_count": count, "eval_count": 3, "load_duration": load_ns,
                                "eval_duration": 30_000_000, "prompt_eval_duration": 50_000_000}])
    return _scn


class Rig(M.Rig):
    def __enter__(self):
        self._added = [k for k in EXTRA if k not in M.MODELS]
        M.MODELS.update({k: v for k, v in EXTRA.items() if k in self._added})
        try:
            return super().__enter__()
        except Exception:
            self._drop()
            raise

    def _drop(self):
        for k in self._added:
            M.MODELS.pop(k, None)

    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            self._drop()

    def script(self, model: str, scn) -> None:
        self.mock.scenarios[model] = scn

    def run_answering(self, session, commands: list, decide) -> list:
        """The worker pump with the session interactive: `decide(event)` answers each approval card
        (it returns the decision dict, or None to leave it)."""
        session.interactive = True
        q: "queue.Queue" = queue.Queue()
        for c in commands + [None]:
            q.put(c)
        seen: list = []

        def sink(ev):
            seen.append(ev)
            if ev.kind == "approval_request":
                got = decide(ev)
                if got is not None:
                    threading.Timer(0.05, session.resolve_approval, args=(ev.data["id"], got)).start()
        session.run(q, sink)
        return seen


def fill_to(session, tokens: int) -> None:
    """Pad the history with note pairs to about `tokens` tokens (chars / 3.5)."""
    pairs = max(1, int(tokens * 3.5 / 2900))
    M.fill(session, pairs)


def chats(rig, model=None) -> list:
    return rig.chats(model)


def last_user(body: dict) -> str:
    users = [m for m in body.get("messages") or [] if m.get("role") == "user"]
    return users[-1].get("content") or "" if users else ""
