"""tests.test_copilot_ref -- `cp:work` in the harness (Halo 3.3.17.0 R2): the ref parses (and only `cp:work`); the
catalog row appears once signed in, with `takes: text, files, web`, `tools: no`, no context, no dollar price; `halo
models` lists it; Auto picks it for a `work-data` need when signed in, never for a role that needs tools, never
without the need, and says so when not signed in; a bio may ask for `work-data`; a session runs ON `cp:work`: two
turns of one conversation (the second carries the contextId), no tools on the wire; not signed in, its one line.
Mock server only.

Run: python -m tests.test_copilot_ref
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


@test
def test_the_ref_parses(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import InvalidModelError
    ref = parse_model_ref("cp:work")
    ctx.check(f"cp:work -> copilot, got {ref}", (ref.provider, ref.model, ref.dialect) == ("copilot", "work", "copilot"))
    try:
        parse_model_ref("cp:gpt")
        ctx.check("cp:gpt refused", False)
    except InvalidModelError as e:
        ctx.check(f"another cp: name says the one model, got {e}", "cp:work" in str(e))


def _rows():
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_enumeration import build_model_rows
    return [r for r in build_model_rows(bridge_home(), env={}) if r.get("ref") == "cp:work"]


@test
def test_the_catalog_row_and_its_takes(ctx: Ctx):
    from halo_harness.model_takes import takes_words
    with CopilotRig() as r:
        ctx.check("not signed in: no cp:work row", _rows() == [])
        r.signin()
        rows = _rows()
        ctx.check(f"signed in: one row, got {len(rows)}", len(rows) == 1)
        row = rows[0]
        ctx.check(f"takes text, files, web, got {takes_words(row)}", takes_words(row) == ["text", "files", "web"])
        ctx.check("tools: no; context unknown; no dollar price", row["tools"] is False and row["context_tokens"] is None
                  and row["price_in_per_m"] is None and row["price_out_per_m"] is None and "$" not in row["detail"])
        ctx.check(f"the price words, got {row['detail']!r}", "Copilot Credits or your licence" in row["detail"]
                  and "research over your work data" in row["detail"])
        from halo_harness.catalog_cli import cmd_models
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                cmd_models([])
            except SystemExit:
                pass
        text = out.getvalue()
        line = next((ln for ln in text.splitlines() if "cp:work" in ln), "")
        ctx.check(f"`halo models` lists it with its takes, got {line!r}", "cp:work" in line and "text,files,web" in line)


@test
def test_auto_and_the_work_data_need(ctx: Ctx):
    from halo_harness.agents_yaml import validate_agent_bio
    from halo_harness.models_auto import pick
    from halo_harness.models_best_at import entry_for
    from halo_harness.providers.copilot_catalog import row
    rows = {"cp:work": entry_for(row()),
            "or:vendor/tooly": {"facts": {"tools": True, "modalities_in": ["text"], "modalities_out": ["text"],
                                          "price_in_per_m": 1.0, "price_out_per_m": 2.0}, "scores": {"code": 0.8, "bulk": 0.6}}}
    with CopilotRig() as r:
        p = pick(None, needs=["work-data"], rows=rows, main_ref="or:vendor/tooly")
        ctx.check(f"not signed in: main's model, the reason says work-data, got {p.ref} {p.reason!r}",
                  p.ref == "or:vendor/tooly" and p.fallback and "work-data" in p.reason)
        r.signin()
        p = pick(None, needs=["work-data"], rows=rows, main_ref="or:vendor/tooly")
        ctx.check(f"signed in: cp:work, a consult role, got {p.ref} {p.reason!r}", p.ref == "cp:work" and not p.fallback
                  and "research over your work data" in p.reason and "no tools" in p.reason)
        for needs in (["work-data", "tools"], ["tools"], []):
            p = pick(None, needs=needs, rows=rows, main_ref="or:vendor/tooly")
            ctx.check(f"needs {needs}: never cp:work, got {p.ref}", p.ref != "cp:work")
        bio = {"name": "work-researcher", "models": {"preference": "auto", "needs": ["work-data"]}}
        ctx.check(f"a bio may ask for work-data, got {validate_agent_bio(bio, name='work-researcher')}",
                  not validate_agent_bio(bio, name="work-researcher"))


@test
def test_a_session_runs_on_cp_work(ctx: Ctx):
    from halo_harness import headless
    with CopilotRig() as r:
        r.signin()
        build = headless.build_session(cwd=REPO, model_ref_raw="cp:work", bare=True, print_mode=True, max_turns=3)
        s = build.session
        evs = list(s.turn("what is on my calendar tomorrow"))
        text = "".join(str(e.data.get("text") or "") for e in evs if e.kind in ("text_delta", "text"))
        ctx.check(f"Copilot answered the turn, got {text[:120]!r}", "Work IQ heard: what is on my calendar tomorrow" in text
                  and "[1] Q3 plan.docx" in text)
        list(s.turn("and the day after"))
        calls = r.mock.calls("/a2a")
        ctx.check(f"two turns, one conversation, got {len(calls)}", len(calls) == 2
                  and calls[1][3]["params"]["message"].get("contextId") == "ctx-1")
        ctx.check("the second turn sent only the new user text", calls[1][3]["params"]["message"]["parts"][0]["text"]
                  .startswith("and the day after"))
        _s, _m, _t, body = s._derive_and_build()
        ctx.check(f"no tools on the wire, got {len(body.get('tools') or [])}", not body.get("tools"))


@test
def test_a_session_not_signed_in_says_one_line(ctx: Ctx):
    from halo_harness import headless
    with CopilotRig() as r:
        s = headless.build_session(cwd=REPO, model_ref_raw="cp:work", bare=True, print_mode=True, max_turns=2).session
        errs = [e.data.get("message") for e in s.turn("hello") if e.kind == "error"]
        ctx.check(f"the line as it is, once, no HTTP status in front, got {errs}",
                  errs == ["Copilot: not signed in -- run `halo copilot signin`."] and not r.mock.requests)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
