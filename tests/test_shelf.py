"""tests.test_shelf -- Halo 3.3.6.0 R4 deliverable 4, the model shelf (models_library/shelf.py, studio/
local_shelf_api.py, models_shelf_cli.py) on the fake Ollama `box` (tests/helpers/local_api_rig.py; never a real
server, never the real ~/.halo):

1. the facts: last used (the ledger's newest answered call), size, picked by a role (a small / compaction call, or a
   role naming it), never used; the hint "not used in 30 days, 17 GB" / "never used, ..." on the Models rows;
2. Retire = the existing delete (the uses card first: 422 when a role uses it, 409 while a live session is on it,
   force) -> the delete call on the fake and one line in <state>/ollama/shelf.jsonl with the re-pull line;
3. the Shelf list and Re-pull = the existing pull job (the model back on the fake, off the shelf); a fitted twin's
   line is its recipe (409);
4. `halo models retire` / `halo models shelf [--repull]`.
Run: python -m tests.test_shelf
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.control_env import QWEN_SHOW  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_local_control_api import Box  # noqa: E402

test, TESTS = new_registry()


def _call(h, model: str, ago_days: float, kind: str = "turn") -> None:
    from halo_harness.ollama_steward.ledger import blank_line, now_iso, record_call
    record_call(h.state, blank_line(host={"name": "box", "url": h.mock.base_url}, model=model, status=200, kind=kind,
                                    at=now_iso(time.time() - ago_days * 86400)))


@test
def test_the_facts_and_the_hint(ctx: Ctx):
    from halo_harness.models_library.shelf import facts
    with Box() as h:
        from halo_harness.ollama_steward.ledger import read_calls
        called = {x.get("model") for x in read_calls(h.state)}
        a, b = "old:7b", "helper:1b"
        _call(h, a, 40)
        _call(h, b, 1, kind="small")
        rows = [{"model": m, "size": 17 * 10 ** 9} for m in (a, b, "unused:3b")]
        f = facts(h.state, "box", rows, config_uses=False)
        ctx.check(f"{a}: last used 40 days ago, the hint, got {f[a]}", f[a]["idle_days"] == 40 and not f[a]["never_used"]
                  and f[a]["hint"] == "not used in 40 days, 17.0 GB" and f[a]["picked"] is False)
        ctx.check(f"{b}: a small call picked it, used yesterday, no hint, got {f[b]}", f[b]["picked"] and f[b]["hint"] == "")
        ctx.check(f"a model with no call: never used, got {f['unused:3b']}", f["unused:3b"]["never_used"]
                  and f["unused:3b"]["hint"] == "never used, 17.0 GB")
        rows_page = next(x for x in h.api("GET", "local/models")[1]["hosts"] if x["name"] == "box")["models"]
        never = [r for r in rows_page if r["model"] not in called]
        ctx.check(f"the Models rows carry the shelf facts and the hint, got {[r.get('shelf') for r in rows_page][:2]}",
                  all(r.get("shelf") is not None for r in rows_page)
                  and all((r["shelf"].get("hint") or "").startswith("never used") for r in never))
        code, got = h.api("GET", "local/host/box/shelf")
        ctx.check(f"GET local/host/box/shelf, got {code}", code == 200 and set(got["facts"]) == set(h.tags()))


@test
def test_retire_the_uses_card_the_delete_and_the_shelf_line(ctx: Ctx):
    with Box() as h:
        cfg = h.config()
        cfg["roles"] = {"reviewer": "ol:qwen3-coder:30b@box"}
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        code, body = h.api("POST", "local/host/box/retire", {"name": "qwen3-coder:30b", "why": "too big"})
        ctx.check(f"422 with the uses card, got {code} {body.get('error')}", code == 422 and body["uses"]["roles"] == ["reviewer"]
                  and body["cli"] == "halo models retire qwen3-coder:30b --host box --force" and not h.mock.deleted)
        h.live.append({"session_id": "s1", "title": "on it", "model": "ol:qwen3-coder:30b@box"})
        code, _b = h.api("POST", "local/host/box/retire", {"name": "qwen3-coder:30b", "force": True})
        ctx.check(f"409 while a live session is on it, got {code}", code == 409 and not h.mock.deleted)
        h.live.clear()
        code, body = h.api("POST", "local/host/box/retire", {"name": "qwen3-coder:30b", "force": True, "why": "too big"})
        ctx.check(f"retired: the delete call on the fake, got {code} {h.mock.deleted} {body.get('say')}",
                  code == 200 and h.mock.deleted == ["qwen3-coder:30b"] and "qwen3-coder:30b" not in h.tags()
                  and "re-pull: ollama pull qwen3-coder:30b" in body["say"])
        line = json.loads((h.state / "ollama" / "shelf.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        ctx.check(f"one shelf line, got {line}", line["model"] == "qwen3-coder:30b" and line["host"] == "box"
                  and line["why"] == "too big" and line["repull"] == "ollama pull qwen3-coder:30b" and line["retired_at"])
        code, got = h.api("GET", "local/shelf")
        ctx.check(f"the Shelf list, got {got.get('shelf')}", code == 200 and [r["model"] for r in got["shelf"]] == ["qwen3-coder:30b"])
        ctx.check("an unknown host: 404", h.api("POST", "local/host/nope/retire", {"name": "x"})[0] == 404)
        ctx.check("no name: 422", h.api("POST", "local/host/box/retire", {})[0] == 422)


@test
def test_repull_is_the_pull_job(ctx: Ctx):
    from halo_harness.models_library.shelf import _append
    with Box() as h:
        h.mock.pullable["qwen3-coder:30b"] = json.loads(json.dumps(QWEN_SHOW))
        h.api("POST", "local/host/box/retire", {"name": "qwen3-coder:30b", "force": True})
        code, v = h.api("POST", "local/shelf/repull", {"host": "box", "model": "qwen3-coder:30b"})
        ctx.check(f"re-pull: a pull job, got {code} {v.get('cli')}", code == 200 and v.get("job")
                  and v["cli"] == "halo models shelf --repull qwen3-coder:30b --host box")
        end = h.wait(v["job"])
        ctx.check(f"the model is back on the fake, got {end.get('ok')} {h.mock.pulled}", end.get("ok")
                  and "qwen3-coder:30b" in h.mock.pulled)
        ctx.check("and off the shelf", h.api("GET", "local/shelf")[1]["shelf"] == [])
        _append(h.state, {"model": "fast-twin:30b", "host": "box", "retired_at": "2026-10-30T00:00:00Z", "why": "x",
                          "repull": "halo models twin qwen3-coder:30b --window 65536 --host box"})
        code, body = h.api("POST", "local/shelf/repull", {"host": "box", "model": "fast-twin:30b"})
        ctx.check(f"a twin's recipe: 409 with the line, got {code} {body.get('error')}", code == 409
                  and "halo models twin qwen3-coder:30b --window 65536" in body["error"])
        ctx.check("not on the shelf: 404", h.api("POST", "local/shelf/repull", {"host": "box", "model": "nope"})[0] == 404)


@test
def test_the_cli(ctx: Ctx):
    import contextlib
    import io
    from halo_harness.catalog_cli import cmd_models

    def run(*argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cmd_models(list(argv))
        return code, out.getvalue()
    with Box() as h:
        model = [m for m in h.tags() if m != "qwen3-coder:30b"][0]
        code, text = run("retire", model, "--host", "box", "--why", "never used")
        ctx.check(f"halo models retire, got {code} {text!r}", code == 0 and f"retired {model} from box" in text
                  and model in h.mock.deleted)
        code, text = run("shelf", "--host", "box")
        ctx.check(f"halo models shelf: the installed and the retired, got {code} {text!r}", code == 0
                  and "installed on box:" in text and "on the shelf (retired):" in text and f"{model} from box" in text)
        code, text = run("shelf", "--json")
        ctx.check("--json", code == 0 and json.loads(text)["shelf"][0]["model"] == model)
        code, text = run("shelf", "--repull", "nope")
        ctx.check(f"--repull of a model not on the shelf, got {code}", code == 1 and "not on the shelf" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
