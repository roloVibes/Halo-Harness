"""tests.test_ollama_log_recovery -- Halo 3.3.6.0 R3 deliverable 3, "the log drives recovery" (agent/
ollama_log_recovery.py; plans/local-model-fit-brief.md D3 item 14) through the loop rig (tests/helpers/
model_switch_rig.py: a real Session over a fake Ollama on 127.0.0.1:0, so the host is served here and its log is this
home's server.log). The fixture lines are appended between the call and the read (ollama_log_recovery.SEAMS
"before_read"), stamped now:

1. `prompt-trimmed`: the log's exact limit / prompt / keep drive trim_recovery -- "the log shows the prompt was cut at
   2,050 of 23,536 tokens", re-sent with a window that holds the real prompt; the ledger line's `log_events`;
2. `cpu-spill`: one line with the layers and a fit option;
3. a crash (FA + q8_0 KV + a spill -> CUDA IMA): its fingerprint at once and the line naming it;
4. `reply-cut`: the reply reserve line;
5. no log: no line, no change, `log_events` None;
6. the preflight's evidence: the log's last cut of this model makes the next send a decision before the bad answer.
Run: python -m tests.test_ollama_log_recovery
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()
from tests.helpers.model_switch_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _now(offset: float = 0.0) -> str:
    return (dt.datetime.now().astimezone() + dt.timedelta(seconds=offset)).isoformat(timespec="milliseconds")


def _gin(status: int = 200) -> str:
    return f"[GIN] {dt.datetime.now():%Y/%m/%d - %H:%M:%S} | {status} | 1.2s | 127.0.0.1 | POST \"/api/chat\""


TRIM = 'time={t} level=WARN source=llama_server.go:334 msg="truncating input prompt" limit=2050 prompt=23536 keep=4 new=2050'
SPILL = ['time={t} level=INFO source=llama_server.go:457 msg="starting llama-server" cmd="llama-server --model /blobs/sha256-0 '
         '-c 32768 -np 1 --cache-type-k q8_0 --flash-attn on"', "load_tensors: offloaded 40/49 layers to GPU"]
CRASH = ["load_tensors: offloaded 59/66 layers to GPU", "CUDA error: an illegal memory access was encountered",
         'time={t} level=ERROR source=server.go:1520 msg="llama runner terminated" error="exit status 0xc0000409"']
CUT = ["slot      release: id  0 | task 8665 | stop processing: n_tokens = 65535, truncated = 1"]


class _Log:
    """Appends `lines` (stamped now) to this home's server.log before the first read after a call, once."""

    def __init__(self, lines: list, times: int = 1) -> None:
        self.lines, self.left = lines, times

    def __enter__(self):
        from halo_harness.agent import ollama_log_recovery as L
        from halo_harness.ollama_steward.hardware_readers import server_log_path
        self.path = server_log_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f'time={_now(-3600)} level=INFO msg="server config" env="map[]"\n', encoding="utf-8")
        L.SEAMS["before_read"] = self._append
        return self

    def _append(self, _session) -> None:
        lines = self.lines if self.left > 0 else []  # the fixture once; every call has its request and [GIN] lines
        self.left -= 1
        body = "".join((x.format(t=_now()) if "{t}" in x else x) + "\n" for x in lines) + _gin() + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f'time={_now()} level=INFO msg="request"\n' + body)

    def __exit__(self, *exc):
        from halo_harness.agent import ollama_log_recovery as L
        L.SEAMS.pop("before_read", None)


def _say(text):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


def _lines(evs) -> list:
    return [(e.data.get("text") or e.data.get("message") or "").replace("↳ ", "") for e in evs
            if e.kind in ("turn_marker", "error")]


def _ledger(state) -> list:
    p = Path(state) / "ollama" / "traffic.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


@test
def test_a_logged_trim_drives_the_recovery(ctx: Ctx):
    # 3.3.16.0 R3: Halo's own prompt passed 32,768 tokens (one more tool), so the first send is already 65k; the model
    # gets room above it (131k) so the log's cut still drives a re-send rather than a compaction
    from tests.helpers import model_switch_rig as R
    saved = R.MODELS["big:30b"]
    R.MODELS["big:30b"] = (131072, saved[1])
    try:
        with Rig() as rig, _Log([TRIM]):
            s = rig.session("ol:big:30b@lan")
            evs = rig.run(s, [_say("hello")])
            chats = rig.chats("big:30b")
            led = _ledger(rig.state_dir)
            kept = dict((getattr(s, "_ollama_log_trims", None) or {}).get("big:30b") or {})
    finally:
        R.MODELS["big:30b"] = saved
    said = [x for x in _lines(evs) if "the log shows the prompt was cut" in x]
    ctx.check(f"the exact cut is said, got {_lines(evs)}", len(said) == 1 and "2,050 of 23,536 tokens" in said[0]
              and "(the request's window 4,096)" in said[0])
    ctx.check(f"re-sent once with a window that holds the real prompt, got {[c.get('options', {}).get('num_ctx') for c in chats]}",
              len(chats) == 2 and (chats[1].get("options") or {}).get("num_ctx", 0) >= 23536 + 1024)
    ctx.check(f"the ledger line carries the log's kinds, got {[x.get('log_events') for x in led]}",
              led and "prompt-trimmed" in (led[0].get("log_events") or []))
    ctx.check(f"the session keeps the cut and Halo's estimate for the preflight, got {kept}", kept.get("prompt") == 23536
              and kept.get("limit") == 2050 and isinstance(kept.get("estimate"), int) and not any(
                  "trimmed the request again" in x for x in _lines(evs)))


@test
def test_the_preflight_takes_the_log_as_evidence(ctx: Ctx):
    import time
    from types import SimpleNamespace
    from halo_harness.agent.preflight import check
    choice = SimpleNamespace(fits=True, ceiling=32768)
    last = {"estimate": 22000 + 4096, "reserve": 4096, "choice": choice, "model": "big:30b", "host_name": "lan"}
    s = SimpleNamespace(_ollama_window_state={"last": last})
    before = check(s)
    s._ollama_log_trims = {"big:30b": {"limit": 2050, "prompt": 23536, "keep": 4, "window_sent": 4096,
                                       "estimate": 15000 + 4096, "reserve": 4096, "at": time.time()}}
    after = check(s)
    ctx.check("no evidence: a request that fits is sent as before", before is None)
    ctx.check(f"the log's cut makes it a decision before the bad answer, got {after}", after is not None and after["cut"]
              and after["prompt"] > 32768 and "the log cut this model's prompt at 2,050 of 23,536 tokens" in after["line"])


@test
def test_a_spill_and_a_reply_cut_are_said(ctx: Ctx):
    with Rig() as rig, _Log(SPILL):
        evs = rig.run(rig.session("ol:big:30b@lan"), [_say("hello")])
    with Rig() as rig, _Log(CUT):
        cut = rig.run(rig.session("ol:big:30b@lan"), [_say("hello")])
    spill = [x for x in _lines(evs) if "spilled to the CPU" in x]
    ctx.check(f"one spill line with the layers and a fit option, got {_lines(evs)}", len(spill) == 1
              and "40/49 layers on the GPU" in spill[0] and ("window" in spill[0] or "twin" in spill[0]))
    ctx.check(f"the reply reserve line, got {_lines(cut)}", any("the log shows a reply stopped at 65,535 tokens" in x
                                                                and "reply reserve" in x for x in _lines(cut)))


@test
def test_a_crash_is_fingerprinted_at_once(ctx: Ctx):
    with Rig() as rig, _Log(CRASH):
        evs = rig.run(rig.session("ol:big:30b@lan"), [_say("hello")])
        from halo_harness.ollama_steward.fingerprints import read
        fps = read(rig.state_dir, host="lan")
        led = _ledger(rig.state_dir)
    line = [x for x in _lines(evs) if "crashed here on" in x]
    ctx.check(f"a fingerprint written at once, got {[(f.get('model'), f.get('signature')) for f in fps]}",
              len(fps) == 1 and fps[0].get("signature") == "CUDA IMA" and fps[0].get("model") == "big:30b")
    ctx.check(f"the failure line names it, got {_lines(evs)}", len(line) == 1 and "halo ollama crashes --why" in line[0])
    ctx.check(f"the ledger's log_events, got {[x.get('log_events') for x in led]}", led and "gpu-memory" in (led[0].get("log_events") or []))


@test
def test_a_remote_host_over_ssh_once_its_read_answered(ctx: Ctx):
    import time
    from types import SimpleNamespace
    from halo_harness.agent.ollama_log_recovery import read_for_call
    from halo_harness.ollama_steward.server_log_remote import read_new_remote
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from tests.helpers.logs_rig import LogsHome
    pc = {"name": "pc", "url": "http://192.0.2.10:11434", "ssh": "example@192.0.2.10"}
    with LogsHome(hosts=[pc]) as h:
        fake = h.remote("pc")
        fake.write("server.log", f'time={_now(-60)} level=INFO msg="start"\n'.encode())
        host = next(x for x in resolve_ollama_hosts() if x.name == "pc")
        s = SimpleNamespace(state_dir=h.state)
        before = read_for_call(s, host, "big:30b", time.time() - 5)  # never read over ssh yet: not readable
        read_new_remote(h.state, host)
        fake.append("server.log", (TRIM.format(t=_now()) + "\n" + _gin() + "\n").encode())
        s2 = SimpleNamespace(state_dir=h.state)
        first = read_for_call(s2, host, "big:30b", time.time() - 5)
        calls = [c for c in fake.calls if "t=65536" in c[2]]
        s2._ollama_log_read = None
        again = read_for_call(s2, host, "big:30b", time.time() - 5)
    ctx.check(f"a host whose ssh read never answered is not read after a call, got {before}", before is None)
    ctx.check(f"once it answered: one ssh read of the newest 64 KB, the cut, got {first and first['kinds']} {len(calls)}",
              first is not None and "prompt-trimmed" in first["kinds"] and len(calls) == 1)
    ctx.check(f"the next call's read does not read the same lines again, got {again and again['kinds']}",
              again is not None and again["kinds"] == [])


@test
def test_no_log_no_change(ctx: Ctx):
    with Rig() as rig:
        from halo_harness.ollama_steward.hardware_readers import server_log_path
        gone = not server_log_path().exists()
        evs = rig.run(rig.session("ol:big:30b@lan"), [_say("hello")])
        led = _ledger(rig.state_dir)
        chats = rig.chats("big:30b")
    ctx.check("no log file in this home", gone)
    ctx.check(f"no log line, one call, log_events None, got {_lines(evs)} {[x.get('log_events') for x in led]}",
              not any("the log shows" in x for x in _lines(evs)) and len(chats) == 1 and led and led[0].get("log_events") is None)


@test
def test_an_hf_local_call_reads_its_servers_log_the_same_way(ctx: Ctx):
    """3.3.8.0 R2: the ledger's writer hands an OpenAI-dialect local call to agent/server_log_recovery.py: the lines of
    this call in the server's own log (llama-server, Halo's process log) go on its ledger line, a crash is
    fingerprinted at once with Halo's launch command, and the turn says one line each."""
    from types import SimpleNamespace
    from halo_harness.agent import server_log_recovery as R
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.ledger_call import observe_call
    from tests.helpers.servers_seed import LLAMA_CRASH, Home

    def _call(session, appended: str):
        R.SEAMS["before_read"] = lambda _s: h.append(h.llama_log, appended)
        req = SimpleNamespace(route=SimpleNamespace(provider="huggingface", dialect="openai-chat", upstream_model="qwen3-8b"),
                              creds=SimpleNamespace(base_url="http://127.0.0.1:8080/v1"), body={"model": "qwen3-8b", "messages": []})
        gen = iter([{"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 4560,
                                                                                            "output_tokens": 40}}])
        list(observe_call(session, req, gen))
        return R.after_call(session)
    with Home(lms=False, mlx=False, pid=None) as h:
        try:
            s = SimpleNamespace(state_dir=h.state, log=SimpleNamespace(session_id="hf-1"), turn_count=1, model_ref=None)
            said = _call(s, "slot update_slots: id  0 | task 7 | input truncated, n_ctx = 8192, n_keep = 0, n_left = 8192\n"
                            "srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 200\n")
            led = read_calls(h.state)
            ctx.check(f"the ledger line carries the log's kinds, got {[x.get('log_events') for x in led]}",
                      led and led[-1].get("log_events") == ["prompt-trimmed"])
            ctx.check(f"the turn says it, got {said}", said and said[0].startswith("the log of llama-8080 shows llama-server cut"))
            said = _call(s, LLAMA_CRASH)
            fps = read(h.state, host="llama-8080")
            ctx.check(f"a crash: its fingerprint at once with Halo's launch command, got {fps[:1]}", fps
                      and "--alias qwen3-8b" in (fps[0].get("load_cmd") or "") and fps[0].get("runtime") == "llama-server")
            ctx.check(f"the turn names the crash, got {said}", any("halo ollama crashes --why" in x for x in said))
            s2 = SimpleNamespace(state_dir=h.state, log=SimpleNamespace(session_id="hf-2"), turn_count=1, model_ref=None)
            req = SimpleNamespace(route=SimpleNamespace(provider="huggingface", dialect="openai-chat", upstream_model="m"),
                                  creds=SimpleNamespace(base_url="http://127.0.0.1:8090/v1"), body={"model": "m", "messages": []})
            list(observe_call(s2, req, iter([{"type": "message_delta", "delta": {}, "usage": {}}])))
            ctx.check("a server with no readable log: log_events None, nothing said",
                      read_calls(h.state)[-1].get("log_events") is None and R.after_call(s2) == [])
        finally:
            R.SEAMS.pop("before_read", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
