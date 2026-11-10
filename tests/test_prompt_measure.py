"""tests.test_prompt_measure -- Halo 3.3.16.1 "the local prompt diet": what a first turn costs before it is
sent (agent/prompt_measure.py) and everywhere it is shown. In-process, a fake home of its own (its MEMORY.md
and topic files), never a server or a model call:

1. `first_turn`: the composition, the reply's room, the window it goes out at, a row per tool (offered or
   left out and why);
2. `halo local prompt <ref> --window N` prints the line and the rows; `--json` the measure;
3. `/status` gains "Halo's own first turn: N tokens of W (P %)" on a local model (not on a cloud one);
   `halo doctor`'s default-model row the same note;
4. Studio's model card: a row "Halo's first turn: N tokens (P % of the window)" in its `how` list;
5. the steward: `prompt-heavy` past half the window, with one next step (the lean profile on, a bigger
   window, the core tools); the fit plan's floor is the measured first turn.
Run: python -m tests.test_prompt_measure
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_measure-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:9")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_HOME: dict = {}


class _In:
    """The working directory for one block (the CLI and Studio's card measure the process's cwd), put back after."""

    def __init__(self, path):
        self.path, self.was = path, None

    def __enter__(self):
        self.was = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, *exc):
        os.chdir(self.was)


def _proj() -> Path:
    if "fh" not in _HOME:
        from tests.helpers.fake_home import build_fake_home
        _HOME["fh"] = build_fake_home()
        os.environ["BRIDGE_TEST_HOME"] = str(_HOME["fh"]["home"])
    return _HOME["fh"]["proj"]


@test
def test_first_turn_says_what_it_is_made_of(ctx: Ctx):
    from halo_harness.agent.prompt_measure import first_turn, first_turn_line
    m = first_turn("ol:qwen3-coder:30b@lan", window=32768, platform="win32", cwd=_proj())
    rows = {r["name"]: r for r in m["tools"]}
    ctx.check(f"the parts add up to the prompt, got {m['line']}", m["line"].startswith(f"prompt {m['prompt']:,}: system "))
    ctx.check(f"the room and the window, got {m['reply_room']} {m['sent_window']}", (m["reply_room"], m["sent_window"]) == (8192, 32768))
    ctx.check("Task: the same tool as Agent", not rows["Task"]["offered"] and "the same tool as Agent" in rows["Task"]["why"])
    ctx.check("PowerShell or Bash: the other shell, reachable", any(not rows[s]["offered"] and "ToolSearch" in rows[s]["why"]
                                                                    for s in ("PowerShell", "Bash")))
    ctx.check(f"the core tools offered as core, got {rows['Read']}", rows["Read"]["offered"] and rows["Read"]["why"] == "core")
    ctx.check(f"the line, got {first_turn_line(m)!r}", first_turn_line(m) ==
              f"Halo's own first turn: {m['prompt']:,} tokens of 32,768 ({m['share']:.0f} %)")


@test
def test_halo_local_prompt_prints_the_line_and_the_rows(ctx: Ctx):
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with _In(_proj()), redirect_stdout(out):
        rc = cmd_local(["prompt", "ol:qwen3-coder:30b@lan", "--window", "49152", "--platform", "linux"])
    text = out.getvalue()
    ctx.check(f"exit 0 and the first-turn line, got {rc} {text[:300]!r}", rc == 0 and "Halo's own first turn:" in text
              and "of 49,152" in text and "reply's room 12,288" in text)
    ctx.check("a row per tool, offered or left out", "  Read " in text and "offered" in text and "left out" in text)
    out = io.StringIO()
    with _In(_proj()), redirect_stdout(out):
        rc = cmd_local(["prompt", "ol:qwen3-coder:30b@lan", "--window", "16384", "--json"])
    got = json.loads(out.getvalue())
    ctx.check(f"--json: the measure, got {sorted(got)[:6]}", rc == 0 and got["sent_window"] == 16384 and got["tools"])


@test
def test_status_and_doctor_say_the_first_turn_on_a_local_model(ctx: Ctx):
    from halo_harness.agent.prompt_measure import composition_text, doctor_note
    from halo_harness.model import parse_model_ref
    comp = {"system": {"tokens": 1, "parts": {"harness": 1, "claude_md": 0, "memory": 0, "topic_index": 0, "tools_schema": 0}},
            "history": {"tokens": 0, "turns": 0}, "user": {"tokens": 1, "parts": {"text": 1, "memory": 0, "topic_index": 0,
                                                                                   "attachments": 0}}, "total": 2}
    local = SimpleNamespace(model_ref=parse_model_ref("ol:qwen3-coder:30b@lan"), _prompt_composition=comp,
                            _measure_window=49152, cwd=_proj())
    text = composition_text(local, first=True)
    ctx.check(f"/status on a local model: the composition, then the first turn, got {text!r}",
              text.startswith("prompt 2:") and "\nHalo's own first turn: " in text and "of 49,152" in text)
    cloud = SimpleNamespace(model_ref=parse_model_ref("ant:claude-opus-5-5"), _prompt_composition=comp, cwd=_proj())
    ctx.check("a cloud model: the composition only", "first turn" not in composition_text(cloud, first=True))
    ctx.check("/cost: the composition only", "first turn" not in composition_text(local))
    note = doctor_note(parse_model_ref("ol:qwen3-coder:30b@lan"), _proj())
    ctx.check(f"halo doctor's default-model row on a local model, got {note!r}", note.startswith(" · Halo's own first turn: "))
    ctx.check("and nothing on a cloud model", doctor_note(parse_model_ref("ant:claude-opus-5-5"), _proj()) == "")


@test
def test_the_model_card_has_the_row(ctx: Ctx):
    from halo_harness.agent.prompt_measure import card_line
    from halo_harness.studio.model_card_api import view
    with _In(_proj()):
        line = card_line("ol:qwen3-coder:30b@lan", 49152)
        card = {"ref": "ol:qwen3-coder:30b@lan", "how": ["calls it with tools"], "window": {"tokens": 49152, "source": "trained"}}
        how = view(card, None)["card"]["how"]
    ctx.check(f"the row, got {line!r}", bool(line) and line.startswith("Halo's first turn: ") and line.endswith("% of the window)"))
    ctx.check(f"a row of its own after the card's own, got {how}", how[0] == "calls it with tools" and how[1] == line)
    ctx.check("a cloud model's card: no row", card_line("ant:claude-opus-5-5", 200000) is None)


def _group(own: int, window: int, cap=None, profile=None) -> dict:
    line = {"at": "2026-11-10T12:00:00Z", "num_ctx_sent": window, "dialect": "ollama", "status": 200,
            "composition": {"system": own // 2, "memory": own // 4, "topic_index": 0, "tools_schema": own - own // 2 - own // 4,
                            "history": 10, "user": 5, "total": own + 15}}
    return {"host": "lan", "model": "qwen3-coder:30b", "key": "lan|qwen3-coder:30b", "cap": cap,
            "profile": profile or {}, "stats": {"native": [line]}}


@test
def test_the_steward_says_prompt_heavy_with_one_next_step(ctx: Ctx):
    from halo_harness.ollama_steward.rules_prompt import prompt_heavy
    from halo_harness.theme import set_config_value, unset_config_value
    ctx.check("under half: nothing", prompt_heavy(_group(6000, 16384), {}) == [])
    f = prompt_heavy(_group(9000, 16384, cap=65536), {})
    ctx.check(f"over half with room to grow: a bigger window, got {f}", len(f) == 1 and f[0]["rule"] == "prompt-heavy"
              and f[0]["proposal"]["field"] == "num_ctx" and f[0]["proposal"]["to"] == 32768)
    f = prompt_heavy(_group(9000, 16384, cap=16384), {})
    ctx.check(f"at the cap: the core tools, got {f[0]['proposal']}", f[0]["proposal"]["field"] == "tools_max")
    set_config_value("prompt.lean", "off")
    try:
        f = prompt_heavy(_group(9000, 16384, cap=65536), {})
    finally:
        unset_config_value("prompt.lean")
    ctx.check(f"the lean profile off: turn it on, got {f[0]['server_hint']}", f[0]["proposal"] is None
              and "prompt.lean auto" in f[0]["server_hint"]["line"])


@test
def test_the_fit_plan_floor_is_the_measured_first_turn(ctx: Ctx):
    from halo_harness.agent.prompt_measure import first_turn, first_turn_floor
    from halo_harness.ollama_steward.fit import FLOOR, floor_window
    with _In(_proj()):
        lean = first_turn("ol:model", window=16384)["prompt"]
        got, planner = first_turn_floor(), floor_window()
    ctx.check(f"Halo's leanest first turn ({lean}) plus a reply, in steps of 4,096, never under 8,192, got {got}",
              got % 4096 == 0 and got >= max(FLOOR, lean + 4096) and got - 4096 < max(FLOOR, lean + 4096))
    ctx.check("the planner reads it", planner == got)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
