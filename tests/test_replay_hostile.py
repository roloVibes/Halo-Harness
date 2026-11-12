"""tests.test_replay_hostile -- Halo 3.4.1.2 (PACKS-7): a hostile `.halo-replay` file someone sends.

- deep nesting (`[` x 200000, or 100 levels of objects) is a ReplayError, never a RecursionError (a 500 on
  `POST replays/import`, a traceback in the CLI);
- ESC / OSC sequences and other control characters in a title or a mark are gone once the file is read
  (`halo replay list / open / compare`, `halo report` print what parse returns) and once it is written;
- importing a file whose id is a saved replay's keeps both: the import gets a new id, the saved one is untouched.
Run: python -m tests.test_replay_hostile
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
OSC = "\x1b]52;c;cHduZWQ=\x07"


def _file(title: str, rid: str = "abc-20261112-120000") -> dict:
    return {"format": "halo-replay", "version": 1, "kind": "session", "id": rid, "session_id": "abc", "title": title,
            "saved": 1.0, "halo": "3.4.1.2", "started": 0.0, "ended": 1.0, "agents": [], "states": [], "costs": [],
            "agent_costs": [], "marks": [{"t": 0.5, "kind": "ask", "agent_id": "main", "text": "mark" + OSC + "\x9b2J"}],
            "bands": [], "plan": None}


@test
def test_packs7_deep_nesting_is_a_replay_error(ctx: Ctx):
    from halo_harness.live.replay_file import ReplayError, parse
    for text, what in (("[" * 200000, "200000 brackets"), (json.dumps(_file("t") | {"x": eval("[" * 100 + "]" * 100)}),
                                                           "100 levels inside a real file")):
        try:
            parse(text)
            got = "parsed"
        except ReplayError as e:
            got = f"ReplayError: {e}"
        except RecursionError:
            got = "RecursionError"
        ctx.check(f"{what}: a ReplayError, got {got[:90]}", got.startswith("ReplayError"))


@test
def test_packs7_control_characters_never_reach_a_terminal(ctx: Ctx):
    from halo_harness.live.replay_file import parse
    p = parse(json.dumps(_file("my run" + OSC + "\x1b[31m")))
    ctx.check(f"the title has no control character, got {p['title']!r}", not any(ord(c) < 32 or 127 <= ord(c) < 160
                                                                                 for c in p["title"]))
    ctx.check(f"nor the mark, got {p['marks'][0]['text']!r}", "\x1b" not in p["marks"][0]["text"]
              and "\x07" not in p["marks"][0]["text"] and "\x9b" not in p["marks"][0]["text"])


@test
def test_packs7_an_import_never_overwrites_a_saved_replay(ctx: Ctx):
    old = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="replay-hostile-")
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.live.replay_file import load, parse, save
        state = bridge_home()
        first = save(state, parse(json.dumps(_file("mine"))))
        incoming = parse(json.dumps(_file("theirs")))
        second = save(state, incoming)
        ctx.check(f"the import got its own file, got {first.name} / {second.name}", first != second and first.exists())
        ctx.check("the saved replay is untouched", load(first)["title"] == "mine" and load(second)["title"] == "theirs")
        ctx.check(f"the caller's payload names the new id, got {incoming['id']}", second.name.startswith(incoming["id"]))
    finally:
        os.environ.pop("BRIDGE_TEST_HOME", None) if old is None else os.environ.__setitem__("BRIDGE_TEST_HOME", old)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
