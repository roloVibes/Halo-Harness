"""tests.test_server_log_hf -- Halo 3.3.8.0 R2: every local server's log is a source for the steward
(ollama_steward/servers_hf.py, server_log_hf.py, log_status_hf.py): the roster (manual, Halo's own, one row per url),
the log source per runtime (Halo's process log, LM Studio's newest server-logs file in a fake folder, a manual `log`
path, the honest line for one that cannot be read), the new lines since the last read through server_log.tail and the
state file, the events written under the server's name, the status line, and a server Halo started whose process is
gone. Fixture logs only: no server runs, nothing is sent.
Run: python -m tests.test_server_log_hf
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.servers_seed import DEAD_PID, Home, hf_line  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_roster_names_every_server_once(ctx: Ctx):
    from halo_harness.ollama_steward.servers_hf import name_for_url, roster
    with Home() as h:
        rows = {s.name: s for s in roster(h.state)}
        ctx.check(f"manual + Halo's, got {sorted(rows)}", sorted(rows) == ["llama-8080", "mac-mlx", "studio"])
        ctx.check("LM Studio is told by its port", rows["studio"].runtime == "lmstudio")
        ctx.check("the entry's runtime and log", rows["mac-mlx"].runtime == "mlx" and rows["mac-mlx"].log == str(h.mlx_log))
        ll = rows["llama-8080"]
        ctx.check(f"Halo's: its log, its launch, its pid, got {ll}", ll.source == "halo" and ll.log == str(h.llama_log)
                  and "--alias qwen3-8b" in (ll.launch or "") and ll.pid == DEAD_PID)
        ctx.check("a ledger url names its server", name_for_url("http://127.0.0.1:8080/v1", h.state) == "llama-8080"
                  and name_for_url("http://localhost:1234/v1", h.state) == "studio")
        ctx.check("an unknown loopback /v1 is auto:<port>", name_for_url("http://127.0.0.1:8000/v1", h.state) == "auto:8000")
        ctx.check("an Ollama url is none of them", name_for_url("http://127.0.0.1:11434", h.state) is None)


@test
def test_a_manual_entry_on_halos_port_keeps_its_name_and_takes_the_log(ctx: Ctx):
    from halo_harness.ollama_steward.servers_hf import roster
    extra = {"huggingface": {"local_servers": [{"name": "box", "url": "http://127.0.0.1:8080/v1"}]}}
    with Home(lms=False, mlx=False, extra=extra) as h:
        rows = roster(h.state)
        ctx.check(f"one row, the entry's name, got {[r.name for r in rows]}", [r.name for r in rows] == ["box"])
        ctx.check("Halo's log and launch on it", rows[0].log == str(h.llama_log) and rows[0].launch)


@test
def test_the_log_source_per_runtime(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_hf import source_for_server
    from halo_harness.ollama_steward.servers_hf import Server
    with Home() as h:
        p, why = source_for_server(h.server("llama-8080"), root=h.root)
        ctx.check(f"Halo's process log, got {p} {why}", p == h.llama_log and why is None)
        p, why = source_for_server(h.server("studio"), root=h.root)
        ctx.check(f"LM Studio: the newest file of its folder, got {p}", p == h.lms_log and why is None)
        p, why = source_for_server(h.server("mac-mlx"), root=h.root)
        ctx.check("the entry's log", p == h.mlx_log)
        p, why = source_for_server(Server("hand", "http://127.0.0.1:8090", "llama-server"), root=h.root)
        ctx.check(f"a hand-started server: the honest line, got {why}", p is None and "not readable from here" in why
                  and "halo local serve" in why and "`log`" in why)
        p, why = source_for_server(Server("lan", "http://192.0.2.30:8080", "llama-server"), root=h.root)
        ctx.check(f"another machine's: on that machine, got {why}", p is None and "on that machine" in why)
    with Home(llama=False, mlx=False) as h:
        import shutil
        shutil.rmtree(h.root / ".lmstudio")
        p, why = source_for_server(h.server("studio"), root=h.root)
        ctx.check(f"no LM Studio folder: where it looked, got {why}", p is None and "server-logs" in why)


@test
def test_new_lines_since_the_last_read_and_events_under_the_server(ctx: Ctx):
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.ollama_steward.server_log_hf import load_state, read_new, scan
    with Home(lms=False, mlx=False) as h:
        s = h.server("llama-8080")
        lines, _st, why = read_new(h.state, s, from_start=True, root=h.root)
        ctx.check(f"from the top: every line, got {len(lines)} ({why})", len(lines) == 22 and why is None)
        written, why = scan(h.state, s, from_start=True, root=h.root)
        kinds = sorted({e["kind"] for e in written})
        ctx.check(f"the kinds, got {kinds}", {"prompt-trimmed", "reply-cut", "cpu-spill", "load-result", "timing"} <= set(kinds))
        ctx.check("written under the server's name, its runtime on each",
                  all(e["host"] == "llama-8080" and e["data"].get("runtime") == "llama-server" for e in written))
        ctx.check("the model from --alias", all(e.get("model") == "qwen3-8b" for e in written))
        st = load_state(h.state).get("llama-8080") or {}
        ctx.check(f"the read position in its own state file, got {st}", st.get("offset") == h.llama_log.stat().st_size)
        h.append(h.llama_log, "slot update_slots: id  0 | task 3 | context shift, n_keep = 0, n_left = 8190, n_discard = 4095\n")
        written, _why = scan(h.state, s, root=h.root)
        ctx.check(f"only the new line, got {[e['kind'] for e in written]}", [e["kind"] for e in written] == ["prompt-trimmed"])
        ctx.check("read_events by the server's name", len(read_events(h.state, host="llama-8080")) >= 6)


@test
def test_the_status_line_for_each_server(ctx: Ctx):
    from halo_harness.ollama_steward.log_status_hf import status
    from halo_harness.ollama_steward.servers_hf import Server
    with Home() as h:
        h.calls(hf_line(ago=30.0))
        st = status(h.state, h.server("llama-8080"), root=h.root)
        ctx.check(f"live: a call and the file just written, got {st['line']}", st["state"] == "live" and st["readable"]
                  and str(h.llama_log) in st["line"])
        ctx.check("its commands", st["halo_cli"] == "halo local log llama-8080 --follow" and st["tail_cli"])
        st = status(h.state, h.server("studio"), root=h.root, now=time.time() + 10 * 86400)
        ctx.check(f"quiet: no calls, an old line, got {st['line']}", st["state"] == "quiet")
        ctx.check("LM Studio's debug said, never done", "Verbose Logging" in st["debug_action"])
        st = status(h.state, Server("hand", "http://127.0.0.1:8090", "llama-server"), root=h.root)
        ctx.check(f"unreadable, the honest line, got {st['line']}", st["state"] == "unreadable"
                  and "start it with `halo local serve` or set `log`" in st["line"])
        st = status(h.state, Server("lan", "http://192.0.2.30:8080", "llama-server"), root=h.root)
        ctx.check(f"on that machine, got {st['line']}", st["line"].startswith("on that machine"))


@test
def test_a_server_halo_started_whose_process_is_gone_is_one_death(ctx: Ctx):
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.server_log_hf import tail_servers
    with Home(lms=False, mlx=False) as h:
        evs = tail_servers(h.state, root=h.root)
        dead = [e for e in evs if (e.get("data") or {}).get("death")]
        ctx.check(f"one death event, got {[e['say'] for e in dead]}", len(dead) == 1 and str(DEAD_PID) in dead[0]["say"])
        ctx.check("the launch command beside it", "--alias qwen3-8b" in (dead[0]["data"].get("launch") or ""))
        fps = read(h.state, host="llama-8080")
        ctx.check(f"a fingerprint, runner died, got {[f.get('signature') for f in fps]}",
                  fps and fps[0]["signature"] == "runner died")
        evs = tail_servers(h.state, root=h.root, now=time.time() + 60)
        ctx.check("the same pid is not said twice", not [e for e in evs if (e.get("data") or {}).get("death")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
