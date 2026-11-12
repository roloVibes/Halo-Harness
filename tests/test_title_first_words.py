"""tests.test_title_first_words -- Halo 3.4.1.1 defect 50: a session's title is the owner's first words, in a session
without a terminal as in the TUI; no model is asked (the prompt-hook call it used demands a JSON verdict, so a session
without a terminal got `{"ok": false, "reason": "Cannot verify file contents; declin` as its title, then its History
row, replay and report card did). A title stored that way by 3.4.1.0 reads as the first words.
Run: python -m tests.test_title_first_words
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
VERDICT = '{"ok": false, "reason": "Cannot verify file contents; declin'
PROMPT = "Do these steps in order. 1) count the lines of a.txt 2) write the total"


class _Session:
    def __init__(self) -> None:
        self.asked: list = []

    def _call_model_for_hook(self, prompt: str, timeout_s: float) -> str:
        self.asked.append(prompt)
        return VERDICT


@test
def test_the_title_is_the_first_words_and_no_model_is_asked(ctx: Ctx):
    from halo_harness.controller import _generate_title
    s = _Session()
    title = _generate_title(s, PROMPT)
    ctx.check(f"the owner's first words, got {title!r}", title == "Do these steps in order. 1)")
    ctx.check("no model was asked (the hook call's JSON verdict can never be a title)", s.asked == [])


@test
def test_a_stored_json_title_reads_as_the_first_words(ctx: Ctx):
    from halo_harness.agent.sessions import _title_for
    from halo_harness.live import history
    d = Path(tempfile.mkdtemp(prefix="title50-"))
    path = d / "s1.jsonl"
    rows = [{"type": "meta", "ts": 1.0, "cwd": str(d)},
            {"type": "user", "ts": 2.0, "content": [{"type": "text", "text": PROMPT}]},
            {"type": "assistant", "ts": 3.0, "content": [{"type": "text", "text": "ok"}]},
            {"type": "meta", "ts": 4.0, "title": VERDICT}]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    got = history.read(path)["title"]
    ctx.check(f"History, the replay, Save and the report card read the first words, got {got!r}",
              got == "Do these steps in order. 1)")
    ctx.check("the session picker's reader skips it too", _title_for(rows) == "")
    rows.append({"type": "meta", "ts": 5.0, "title": "Basket fix"})
    ctx.check("a plain title (a /rename) still wins", history._title(rows) == "Basket fix")
    ctx.check("no title at all stays none", history._title(rows[:3]) == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
