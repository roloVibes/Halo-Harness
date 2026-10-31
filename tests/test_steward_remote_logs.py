"""tests.test_steward_remote_logs -- Halo 3.3.6.0 R3 deliverable 1, "remote logs"
(ollama_steward/server_log_remote.py, log_tail.py; plans/local-model-fit-brief.md D3 item 13). A fake ssh runner
(tests/helpers/fake_ssh_logs.py) answers the read command over a fixture folder that stands for that machine:

1. a rotation set over ssh: the first read starts at the end, the next reads only the new lines (an invalid UTF-8
   byte read as bytes and replaced, never a stop), the state per host across reads, a rotation finishes the old file
   then reads the new one;
2. a Windows host (PowerShell answers once sh does not; the platform is kept) and a systemd Linux (the journal and
   its cursor);
3. the ladder's three rungs: ssh, a fleet member's pushed events, /api/ps only;
4. the steward's job reads every ssh host; `halo ollama events --host`, `halo ollama log [--kind] [--follow]`;
5. never a real ssh: no seam and background reads off, or no ssh entry, is said, not run.
Run: python -m tests.test_steward_remote_logs
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import GIN, LogsHome, T  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PC = {"name": "pc", "url": "http://192.0.2.10:11434", "ssh": "example@192.0.2.10"}
MAC = {"name": "mac", "url": "http://192.0.2.20:11434"}
TRIM = 'time={t} level=WARN source=llama_server.go:334 msg="truncating input prompt" limit=2050 prompt=23536 keep=4 new=2050\n'


def _host(name):
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return next(h for h in resolve_ollama_hosts() if h.name == name)


@test
def test_a_rotation_set_over_ssh_and_its_state(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_remote import host_state, read_new_remote
    with LogsHome(hosts=[PC]) as h:
        fake = h.remote("pc")
        fake.write("server-1.log", b"time=2026-10-28T09:00:00Z level=INFO msg=\"old run\"\n", mtime_s=1000)
        fake.write("server.log", f'time={T(0)} level=INFO msg="server config" env="map[]"\n'.encode())
        host = _host("pc")
        first, why1 = read_new_remote(h.state, host)
        fake.append("server.log", TRIM.format(t=T(5)).encode() + b"a byte that is not UTF-8: \xff\xfe here\n" + b"partial")
        second, why2 = read_new_remote(h.state, host)
        st = host_state(h.state, "pc")
        third, _ = read_new_remote(h.state, host)
        old_bytes = (fake.folder / "server.log").read_bytes() + b" line\n" + f"{GIN(6)}\n".encode()
        (fake.folder / "server.log").unlink()
        fake.write("server-1.log", old_bytes, mtime_s=2000)
        fake.write("server.log", f'time={T(9)} level=INFO msg="server config" env="map[NEW]"\nnew run line\n'.encode())
        calls = len(fake.calls)
        rotated, _ = read_new_remote(h.state, host)
    ctx.check(f"the first read starts at the end, got {first} {why1}", first == [] and why1 is None)
    ctx.check(f"the second read: the new whole lines only, got {second}", len(second) == 2 and "truncating" in second[0])
    ctx.check(f"an invalid byte is replaced, not a stop, got {second[1:]!r}", "�" in second[1] and second[1].endswith("here"))
    ctx.check(f"the state: platform, offset, ok, the newest line's time, got {st}", st.get("platform") == "posix"
              and st.get("offset") and st.get("ok_at") and st.get("last_line_at") and why2 is None)
    ctx.check(f"a third read with nothing new reads nothing, got {third}", third == [])
    ctx.check(f"a rotation: the old file's end, then the new file, got {rotated}", rotated[:2] == ["partial line", GIN(6)]
              and rotated[-1] == "new run line" and len(fake.calls) - calls == 2)
    ctx.check("every read went through the fake: never a real ssh", all(c[:2] == ["sh", "-c"] for c in fake.calls))


@test
def test_a_windows_host_and_a_linux_journal(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_remote import host_state, read_new_remote
    from halo_harness.ollama_steward.log_tail import remote_tail
    win = {**PC, "name": "winbox"}
    lin = {**PC, "name": "linbox", "url": "http://192.0.2.11:11434"}
    with LogsHome(hosts=[win, lin]) as h:
        fake = h.remote("winbox", "windows")
        fake.write("server.log", f'time={T(0)} level=INFO msg="Listening on [::]:11434 (version 0.40.6)"\n'.encode())
        read_new_remote(h.state, _host("winbox"))
        fake.append("server.log", TRIM.format(t=T(3)).encode())
        lines, _ = read_new_remote(h.state, _host("winbox"))
        st = host_state(h.state, "winbox")
        argv0 = [c[0] for c in fake.calls]
        tail, source, _w = remote_tail(_host("winbox"), 5)
        journal = [f"Oct 26 08:00:01 gpubox ollama[812]: time={T(1)} level=INFO msg=\"one\""]
        jfake = h.remote("linbox", "posix", journal=journal)
        first, _ = read_new_remote(h.state, _host("linbox"))
        journal.append(f"Oct 26 08:00:02 gpubox ollama[812]: {TRIM.format(t=T(4)).strip()}")
        second, _ = read_new_remote(h.state, _host("linbox"))
        jst = host_state(h.state, "linbox")
    ctx.check(f"Windows: sh does not answer, PowerShell does, and is kept, got {argv0}",
              argv0 == ["sh", "powershell", "powershell"] and st.get("platform") == "windows")
    ctx.check(f"the Windows path and the new line, got {st.get('path')} {lines}", "AppData\\Local\\Ollama\\server.log" in
              str(st.get("path")) and len(lines) == 1 and "truncating" in lines[0])
    ctx.check(f"the bounded tail names the file, got {source} {tail}", "server.log" in source and len(tail) == 2)
    ctx.check(f"the journal: the first read takes the cursor only, the next the new line, got {first} {second}",
              first == [] and len(second) == 1 and "truncating" in second[0] and jst.get("path") == "journalctl -u ollama"
              and "cursor" in jst)
    ctx.check("the journal's second read asked after the cursor", "--after-cursor" in jfake.calls[-1][2])


@test
def test_the_ladder_three_rungs(ctx: Ctx):
    from halo_harness.fleet.control_probes import take_events
    from halo_harness.ollama_steward.log_status import ladder, status
    with LogsHome(hosts=[PC, MAC, {"name": "far", "url": "http://192.0.2.40:11434"}]) as h:
        h.remote("pc")
        take_events(h.state, "macbook", [{"kind": "prompt-trimmed", "severity": "warn", "say": "cut", "at": T(5),
                                          "model": "qwen3:8b", "host": "local", "addr": "192.0.2.20", "port": 11434}])
        rungs = {n: ladder(h.state, _host(n)) for n in ("pc", "mac", "far")}
        st_far, st_mac = status(h.state, _host("far")), status(h.state, _host("mac"))
    ctx.check(f"ssh, the member's push, /api/ps, got {[r['rung'] for r in rungs.values()]}",
              [r["rung"] for r in rungs.values()] == ["ssh", "member", "api-ps"])
    ctx.check(f"the member rung names the member, got {rungs['mac']}", rungs["mac"].get("member") == "macbook")
    ctx.check(f"/api/ps only says the fit rule, got {st_far['line']!r}", st_far["state"] == "remote-no-ssh"
              and "size_vram < size = spill" in st_far["line"] and "no ssh entry" in st_far["line"])
    ctx.check(f"the member rung's last line is the pushed event's, got {st_mac}", st_mac["state"] == "remote-no-ssh"
              and st_mac.get("last_line_at") and "macbook" in st_mac["line"])


@test
def test_the_job_and_the_cli(ctx: Ctx):
    from halo_harness.ollama_steward import cli_logs
    from halo_harness.ollama_steward.log_tail import tail_remote_hosts
    with LogsHome(hosts=[PC]) as h:
        fake = h.remote("pc")
        fake.write("server.log", f'time={T(0)} level=INFO msg="start"\n'.encode())
        tail_remote_hosts(h.state, 1000.0)
        fake.append("server.log", TRIM.format(t=T(5)).encode() + f"{GIN(6)}\n".encode())
        again = tail_remote_hosts(h.state, 1010.0)
        later = tail_remote_hosts(h.state, 1040.0)
        code, out = h.cli(cli_logs.cmd_ollama_events, "--host", "pc", "--since", "1h")
        code2, log_out = h.cli(cli_logs.cmd_ollama_log, "--host", "pc", "-n", "5", "--kind", "truncation")
        cli_logs.SEAMS.update(rounds=1, sleep=lambda s: fake.append("server.log", f"{GIN(8, 499)}\n".encode()))
        try:
            code3, follow = h.cli(cli_logs.cmd_ollama_log, "--host", "pc", "-n", "5", "--follow")
        finally:
            cli_logs.SEAMS.clear()
    ctx.check(f"the job reads an ssh host every 30 s, got {[e['kind'] for e in later]} (10 s after: {again})",
              again == [] and [e["kind"] for e in later] == ["prompt-trimmed"] and later[0]["host"] == "pc")
    ctx.check(f"events --host lists that host's events, got {out!r}", code == 0 and "prompt-trimmed" in out)
    ctx.check(f"log --kind truncation: the status line, the source, the cut line only, got {log_out!r}", code2 == 0
              and "log of 'pc'" in log_out and "ssh example@192.0.2.10" in log_out and "[truncation]" in log_out
              and "[GIN]" not in log_out)
    ctx.check(f"--follow prints the line that arrived, got {follow.splitlines()[-1:]}", code3 == 0
              and "| 499 |" in follow.splitlines()[-1])


@test
def test_never_a_real_ssh(ctx: Ctx):
    from halo_harness.ollama_steward import server_log_remote as R
    from halo_harness.ollama_steward.server_log import read_new, source_for
    with LogsHome(hosts=[PC, MAC]) as h:
        R.SEAMS.clear()  # no fake: background reads are off, so nothing runs
        run, why = R.runner_for(_host("pc"))
        lines, why2 = R.read_new_remote(h.state, _host("pc"))
        _p, src_why = source_for(_host("mac"))
        _l, _st, new_why = read_new(h.state, _host("mac"))
    ctx.check(f"no seam, background reads off: no runner, got {run} {why!r}", run is None and "background reads are off" in why)
    ctx.check(f"the read says why, got {lines} {why2!r}", lines == [] and "is on that machine" in why2)
    ctx.check(f"no ssh entry is said, got {src_why!r} / {new_why!r}", "no ssh entry" in src_why and "no ssh entry" in new_why)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
