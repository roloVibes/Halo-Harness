"""tests.test_live_recording_redaction -- Halo 3.6.0.3 B (Z1, file 07): Record (Session's Agent panel and the LAST
SESSIONS rows) writes one HTML page a person sends to others, so what it writes passes the session export's redaction
(privacy_redact.redact, the same call `halo session export` stands on): a key-shaped token is masked, a home path reads
`~/...`, the account and machine names are out; the page still holds every agent, state and entry (Play has the same
data). Seed: tests/helpers/replay_seed.py, a made-up account from tests/test_privacy_scrub.py.
Run: python -m tests.test_live_recording_redaction
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.replay_seed import FAKE_KEY, SID, T0, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_privacy_scrub import MACHINE, NIX_HOME, USER, WIN_HOME  # noqa: E402

test, TESTS = new_registry()
SAID = f"read {WIN_HOME}\\Documents\\plan.md and {NIX_HOME}/notes, as {USER} on {MACHINE} {FAKE_KEY}"
BAD = (FAKE_KEY, FAKE_KEY[9:], USER, MACHINE, "Users\\" + USER, "/home/" + USER)


@contextlib.contextmanager
def _home():
    env = {"USERPROFILE": WIN_HOME, "HOME": NIX_HOME, "USERNAME": USER, "USER": USER, "LOGNAME": USER, "COMPUTERNAME": MACHINE}
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + tuple(env)}
    with tempfile.TemporaryDirectory(prefix="halo-record-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.update(env)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _seeded(state: Path) -> "tuple[Path, dict]":
    """The seeded session with one more line in main's log (a person's words holding the three) and its history."""
    from halo_harness.live import history
    path = seed(state)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "ts": T0 + 95, "content": SAID}) + "\n")
    return path, history.read(path)


def _data(page: str) -> dict:
    """The page's JSON block (the data Play draws), decoded."""
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else {}


@test
def test_the_page_masks_the_key_the_home_and_the_names(ctx: Ctx):
    from halo_harness.live import recording
    with _home() as state:
        _path, hist = _seeded(state)
        hist.setdefault("entries", {}).setdefault("main", []).append({"ts": T0 + 96, "kind": "text", "text": SAID})
        page = recording.render(hist, harness="local")
        data = json.dumps(_data(page), ensure_ascii=False)
        ctx.check("the page has its data block", data not in ("{}", "null"))
        for bad in BAD:
            ctx.check(f"{bad[:40]!r} is not in the page's data", bad not in data)
        ctx.check("no key anywhere in the page", FAKE_KEY not in page and FAKE_KEY[9:] not in page)
        ctx.check("the home reads ~", "~/Documents/plan.md" in data and "~/notes" in data)
        ctx.check("where the key stood, the redactor's mark", "<redacted>" in data)
        written = recording.write(state, hist, harness="local").read_text(encoding="utf-8")
        ctx.check("the written file is the rendered page", written == page)


@test
def test_the_page_still_holds_everything_play_draws(ctx: Ctx):
    from halo_harness.live import recording
    with _home() as state:
        _path, hist = _seeded(state)
        got = _data(recording.render(hist, harness="local"))
        ctx.check(f"every agent, got {len(got.get('agents') or [])}", len(got.get("agents") or []) == len(hist["agents"]) > 0)
        ctx.check(f"every state, got {len(got.get('states') or [])}", len(got.get("states") or []) == len(hist["states"]) > 0)
        ctx.check("every agent's entries, the same count",
                  {k: len(v) for k, v in (got.get("entries") or {}).items()} == {k: len(v) for k, v in (hist.get("entries") or {}).items()})
        ctx.check("the session id and the project's name only", got.get("session_id") == SID
                  and got.get("cwd") == Path(str(hist.get("cwd") or "")).name)


@test
def test_the_export_masks_the_same(ctx: Ctx):
    """The session export of the same session (session_trace, the export's three doors) masks the key and the home."""
    from halo_harness.session_trace import trace_markdown
    with _home() as state:
        path, _hist = _seeded(state)
        md = trace_markdown(path)
        ctx.check("the export has the line", "plan.md" in md)
        ctx.check("no key in the export", FAKE_KEY not in md and FAKE_KEY[9:] not in md)
        ctx.check("no home path in the export", WIN_HOME not in md and NIX_HOME + "/" not in md)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="record's redaction"))
