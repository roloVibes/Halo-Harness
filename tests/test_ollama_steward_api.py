"""tests.test_ollama_steward_api -- Halo 3.3.4.0 R5: the Ollama steward's Studio routes (studio/ollama_steward_api.py,
studio/ollama_hosts_view.py) on the fixture state dir of tests/helpers/ollama_panel_seed.py (two hosts, a Hugging
Face local server, the ledger, an event, a note, review mode; the card and the catalog through READERS). In-process
through studio/api.dispatch, a fresh home, background reads off: no server, no model call.

1. GET ollama/steward: the job's status (the model filled as `status` does), the note lines, review mode;
2. GET ollama/hosts: per host the card lines, the models with the fixture's hour numbers, the vision eye, the VRAM
   share, the findings and the fit plan; the local server's rows from its OpenAI-dialect lines;
3. GET ollama/timeline: one bucket per minute, the calls per host, the trim and the cut in their minutes;
4. POST run (review) proposes; apply {id} writes ollama.profiles and the finding says applied; a plan change applies;
   undo reverts; dismiss keeps a finding out of the rules' answer (and of the next GET);
5. the race R4 left open: two passes at once land one change (steward.run's profile lock);
6. the 404 / 405 / 409 / 422 answers.
Run: python -m tests.test_ollama_steward_api
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import ollama_panel_seed as S  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


class Panel(Home):
    def __enter__(self):
        super().__enter__()
        from halo_harness.studio import ollama_hosts_view as V
        S.seed(self.state)
        V.reset_cache()
        V.READERS.clear()
        V.READERS.update(S.readers())
        from halo_harness.ollama_steward import agent
        self._live, self.model_calls = agent.live_call, []
        agent.live_call = lambda *a, **k: self.model_calls.append(a) or {}
        return self

    def __exit__(self, *exc):
        from halo_harness.ollama_steward import agent
        from halo_harness.studio import ollama_hosts_view as V
        agent.live_call = self._live
        V.READERS.clear()
        V.reset_cache()
        return super().__exit__(*exc)

    def api(self, method: str, path: str, body=None, query=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=self.root,
                                state_dir=self.state))

    def host(self, name: str) -> dict:
        return next(h for h in self.api("GET", "ollama/hosts")[1]["hosts"] if h["name"] == name)

    def profiles(self) -> dict:
        return (json.loads((self.state / "config.json").read_text(encoding="utf-8")).get("ollama") or {}).get("profiles") or {}


@test
def test_the_steward_route(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        status, body = p.api("GET", "ollama/steward")
        ctx.check(f"200 with the job's status, got {status} {body.get('status')}", status == 200
                  and body["status"]["running"] is False and body["status"]["model_why"])
        ctx.check(f"the status lines, got {body['status_lines']}", body["status_lines"][0].startswith("steward job: not running"))
        ctx.check(f"the note of the last 24 h, newest last, got {[n.get('say') for n in body['notes']]}",
                  body["notes"][-1]["say"] == S.NOTE and body["notes"][-1]["lines"][-1] == S.COST)
        ctx.check(f"the last note and review mode, got {body['last_note'] and body['last_note']['say']} {body['mode']}",
                  body["last_note"]["say"] == S.NOTE and body["mode"] == "review")
        ctx.check("no job in this process, no hub note, no proposal yet", body["current"] is None
                  and body["hub_note"] is None and body["proposals"] == [] and body["changes"] == [])
        from halo_harness.theme import set_config_value
        set_config_value("ollama.steward.model", "none")  # Settings' "none": no notes on purpose
        st = p.api("GET", "ollama/steward")[1]["status"]
        ctx.check(f"model none: no model, and the status says so, got {st.get('model')} {st.get('model_why')!r}",
                  st.get("model") is None and "is none" in str(st.get("model_why")))
        ctx.check("never a model call", p.model_calls == [])


@test
def test_the_hosts_route(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        status, body = p.api("GET", "ollama/hosts")
        ctx.check(f"200, both hosts, the local server, got {status} {[h['name'] for h in body.get('hosts', [])]}",
                  status == 200 and [h["name"] for h in body["hosts"]] == ["pc", "samus"]
                  and [s["name"] for s in body["local_servers"]] == ["llama-box"])
        pc = body["hosts"][0]
        lines = " | ".join(pc["card_lines"])
        ctx.check(f"the card line: GPU, server settings, ComfyUI, got {lines}", "GPU 0: a 24 GB card" in lines
                  and "KV cache f16" in lines and "other: ComfyUI 2.0 GiB" in lines)
        rows = {m["model"]: m for m in pc["models"]}
        for (host, model), want in S.HOUR.items():
            mine = {h["name"]: {m["model"]: m for m in h["models"]} for h in body["hosts"] + body["local_servers"]}
            got = ((mine.get(host) or {}).get(model) or {}).get("hour") or {}
            ctx.check(f"{host} {model}: the hour's numbers {want}, got {got}", all(got.get(k) == v for k, v in want.items()))
        big = rows[S.BIG]
        ctx.check(f"the 27B: loaded at 90 % VRAM, the eye, 7 calls in 24 h, got {big['loaded']} {big['vision']}",
                  big["loaded"]["vram_pct"] == 90 and big["vision"] is True and big["day_calls"] == 7
                  and big["hour"]["window"] == 32768)
        ctx.check(f"the coder: 5 calls in 24 h, not loaded, no eye, got {rows[S.CODER]}",
                  rows[S.CODER]["day_calls"] == 5 and rows[S.CODER]["loaded"] is None and rows[S.CODER]["vision"] is False)
        rules = sorted(f["rule"] for f in pc["findings"])
        ctx.check(f"the findings on pc, got {rules}", {"window-small", "reply-cut", "cpu-spill"} <= set(rules))
        plan = pc["plan"] or {}
        kinds = [o["kind"] for o in plan.get("options") or []]
        ctx.check(f"the fit plan: they do not fit, one at a time chosen, the KV hint, got {plan.get('says')} {kinds}",
                  plan.get("fits_now") is False and kinds[plan["chosen"]] == "one-at-a-time" and "kv-q8_0" in kinds)
        hf = body["local_servers"][0]
        ctx.check(f"the local server: kind, its window/reserve finding named by the entry, got {hf['kind']} {hf['findings']}",
                  hf["kind"] == "local server" and [f["rule"] for f in hf["findings"]] == ["reply-cut"]
                  and hf["findings"][0]["host"] == "llama-box")
        ctx.check("never a model call", p.model_calls == [])


@test
def test_the_timeline(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        status, body = p.api("GET", "ollama/timeline", query={"host": "pc", "since": "1h"})
        b = body.get("buckets") or []
        ctx.check(f"one bucket per minute for the hour, got {status} {len(b)}", status == 200 and 60 <= len(b) <= 62
                  and body["bucket_s"] == 60)
        ctx.check(f"pc's 10 calls of the hour, got {sum(x['calls'] for x in b)}", sum(x["calls"] for x in b) == 10)
        trims, cuts = [x for x in b if x["trims"]], [x for x in b if x["cuts"]]
        ctx.check(f"the trim and the cut a minute apart, got {trims} {cuts}", len(trims) == 1 and len(cuts) == 1
                  and cuts[0]["t"] - trims[0]["t"] == 60 and cuts[0]["p95_prompt"] == 32000)
        ctx.check("the 500 is an error", sum(x["errors"] for x in b) == 1)
        hf = p.api("GET", "ollama/timeline", query={"host": "llama-box"})[1]["buckets"]
        ctx.check(f"the local server's own lines by its entry name, got {sum(x['calls'] for x in hf)}",
                  sum(x["calls"] for x in hf) == 3)
        everyone = p.api("GET", "ollama/timeline")[1]["buckets"]
        ctx.check("no host: every line of the hour", sum(x["calls"] for x in everyone) == 15)
        ctx.check("a bad span is a 422", p.api("GET", "ollama/timeline", query={"since": "lots"})[0] == 422)


@test
def test_run_apply_undo_and_dismiss(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        plan = p.host("pc")["plan"]  # read before the window grows (the plan then differs)
        change = plan["options"][plan["chosen"]]["changes"][0]
        status, ran = p.api("POST", "ollama/steward/run")
        ctx.check(f"a review pass proposes, never applies, got {status} {ran}", status == 200 and ran["mode"] == "review"
                  and ran["proposed"] >= 1 and ran["applied"] == 0)
        props = p.api("GET", "ollama/steward")[1]["proposals"]
        win = next((x for x in props if x["rule"] == "window-small"), {})
        ctx.check(f"the window proposal is pending, got {[x['id'] for x in props]}", win.get("to") == 65536)
        status, out = p.api("POST", "ollama/steward/apply", {"id": win.get("id")})
        prof = p.profiles().get("pc|qwen3.8:27b") or {}
        ctx.check(f"apply writes the profile, got {status} {out.get('say')} {prof}", status == 200 and out["ok"]
                  and prof.get("num_ctx") == 65536 and prof.get("by") == "steward")
        f = next(x for x in p.host("pc")["findings"] if x["id"] == win["id"])
        ctx.check(f"the finding says applied, got {f.get('applied')}", str(f.get("applied") or "").startswith("c-"))
        left = [x["id"] for x in p.api("GET", "ollama/steward")[1]["proposals"]]
        ctx.check(f"no longer pending, got {left}", win["id"] not in left)
        status, out = p.api("POST", "ollama/steward/apply", {"id": win["id"]})
        ctx.check(f"again within ten minutes: 409 with the reason, got {status} {out}", status == 409
                  and "ten minutes" in out["error"])
        status, out = p.api("POST", "ollama/steward/apply", {**change, "why": "the fit plan: one at a time"})
        ctx.check(f"a plan change applies, got {status} {out.get('say')}", status == 200
                  and (p.profiles().get("pc|qwen3-coder:30b") or {}).get("keep_alive") == "0")
        status, out = p.api("POST", "ollama/steward/undo")
        ctx.check(f"undo reverts the newest change, got {status} {out.get('say')}", status == 200 and out["change"]
                  and "keep_alive" not in (p.profiles().get("pc|qwen3-coder:30b") or {}))
        cut = next(x for x in p.host("pc")["findings"] if x["rule"] == "reply-cut")
        status, out = p.api("POST", "ollama/steward/dismiss", {"id": cut["id"]})
        ctx.check(f"dismiss answers, got {status} {out}", status == 200 and out["dismissed"] == cut["id"])
        ids = [x["id"] for x in p.host("pc")["findings"]]
        ctx.check(f"the finding is gone, and stays gone on the next read, got {ids}", cut["id"] not in ids
                  and cut["id"] not in [x["id"] for x in p.host("pc")["findings"]])
        from halo_harness.ollama_steward import rules, steward
        ctx.check("the rules read the dismissed line too", cut["id"] not in [x["id"] for x in rules.findings(p.state)]
                  and any(r.get("kind") == "dismissed" for r in steward.read_journal(p.state)))
        later = time.time() + steward.DISMISS_S + 60
        ctx.check("after 24 hours it may speak again", cut["id"] not in steward.dismissed(p.state, now=later))
        ctx.check("never a model call", p.model_calls == [])


@test
def test_two_passes_at_once_land_one_change(ctx: Ctx):
    with Panel(hosts=[S.PC, S.SAMUS]) as p:
        from halo_harness.ollama_steward import rules, steward
        found = [f for f in rules.findings(p.state) if f["rule"] == "window-small"]
        slow_check = steward.check

        def slow(*a, **k):
            got = slow_check(*a, **k)
            time.sleep(0.4)  # a pass between its read of the ten-minute mark and its write
            return got
        steward.check = slow
        try:
            ts = [threading.Thread(target=steward.run, args=(p.state,), kwargs={"mode_name": "auto", "found": found,
                                                                                "say": lambda s: None}) for _ in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join(30)
        finally:
            steward.check = slow_check
        applied = [r for r in steward.read_journal(p.state) if r.get("kind") == "apply"]
        ctx.check(f"one apply line, not two, got {len(applied)}", len(applied) == 1)


@test
def test_the_bad_requests(ctx: Ctx):
    with Panel(hosts=[S.PC]) as p:
        ctx.check("an unknown path is a 404", p.api("GET", "ollama/nothing")[0] == 404)
        ctx.check("a GET on a POST route is a 405", p.api("GET", "ollama/steward/apply")[0] == 405)
        ctx.check("apply without an id or a change is a 422", p.api("POST", "ollama/steward/apply", {})[0] == 422)
        ctx.check("dismiss without an id is a 422", p.api("POST", "ollama/steward/dismiss", {})[0] == 422)
        status, out = p.api("POST", "ollama/steward/apply", {"id": "window-small-000000"})
        ctx.check(f"an unknown id is a 409 that says so, got {status} {out}", status == 409 and "no finding" in out["error"])
        status, out = p.api("POST", "ollama/steward/apply", {"key": "elsewhere|m", "field": "num_ctx", "to": 8192})
        ctx.check(f"a plan change for a host not here, got {status} {out}", status == 409 and "not <host>|<model>" in out["error"])
        status, out = p.api("POST", "ollama/steward/apply", {"key": "pc|qwen3.8:27b", "field": "temperature", "to": 1})
        ctx.check(f"a field that is not a profile field, got {status}", status == 409 and "field is one of" in out["error"])
        status, out = p.api("POST", "ollama/steward/undo")
        ctx.check(f"nothing to undo says so, got {out}", status == 200 and out["change"] is None and "nothing to undo" in out["say"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
