"""tests.test_host_ladder -- Halo 3.3.7.0 R1 deliverable 3: the ladder's new rung (ollama_steward/host_client.py,
host_reads.py) and what reads through it, over tests/helpers/host_rig.py's fake host and no ssh:

1. the log status says "via host" (rung host), and a host wins over an ssh entry for reading; unpaired, ssh again;
2. the hardware card arrives through the host (its sources led by "halo host"; `halo ollama hardware` says "via host");
3. the Logs page's tail and status arrive through it (Studio's local/host/<name>/log routes), never a prompt body;
4. a profile shows verified from the host ("the host at <addr>"), the fit evidence reads its events, the fit meter its
   card;
5. a host that does not answer: one line, and it is not asked again for a while;
6. probe and bench through a host answer 409 naming the `control` grant (3.3.7.0 R2: a view-only peer).
Run: python -m tests.test_host_ladder
"""
from __future__ import annotations

import io
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_rig import BIG, PC, HostRig, pc_host  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _api(rig, method: str, path: str, body=None, query=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=Path(rig.root_p),
                            state_dir=rig.peer, server=None))


@test
def test_the_status_says_via_host_and_a_host_wins_over_ssh(ctx: Ctx):
    from halo_harness.ollama_steward.log_status import ladder, status
    with HostRig() as rig:
        rig.start()
        ctx.check("unpaired, no ssh: api-ps", ladder(rig.peer, pc_host())["rung"] == "api-ps")
        rig.pair()
        st = status(rig.peer, pc_host())
        ctx.check(f"paired: rung host, the host's own state, 'via host' in the line, got {st['rung']} {st['line']!r}",
                  st["rung"] == "host" and st["state"] == "live" and "via host 127.0.0.1" in st["line"]
                  and st["via"] == "host" and "server.log" in st["path"])
        rig.set_peer(**{"ollama.hosts": [{**PC, "ssh": "you@192.0.2.10"}]})
        from halo_harness.providers.ollama import resolve_ollama_host
        lad = ladder(rig.peer, resolve_ollama_host("pc"))
        ctx.check(f"with an ssh entry too, the host wins for reading, got {lad}", lad["rung"] == "host")
        from halo_harness.peers import store
        store.remove_host(store.hosts())
        ctx.check("unpaired again: ssh", ladder(rig.peer, resolve_ollama_host("pc"))["rung"] == "ssh")


@test
def test_the_hardware_card_arrives_through_the_host(ctx: Ctx):
    from halo_harness.ollama_steward.cli import cmd_ollama_hardware
    from halo_harness.ollama_steward.hardware import hardware_card
    with HostRig() as rig:
        rig.start()
        rig.pair()
        card = hardware_card(pc_host())
        ctx.check(f"the host's card, its sources led by halo host, got {card.get('via')} {card.get('sources', [])[:1]}",
                  card.get("via") == "host" and card["sources"][0]["reader"] == "halo host"
                  and card["gpus"][0]["name"] == "a 24 GB card" and card["log"]["rung"] == "host")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_ollama_hardware(["--host", "pc"])
        ctx.check(f"halo ollama hardware --host pc says via host, got {rc} {out.getvalue()!r}", rc == 0
                  and "source: via host 127.0.0.1" in out.getvalue() and "22.0 GB usable" in out.getvalue())
        from halo_harness.providers.fit_meter import host_card_of
        ctx.check("the fit meter's host card reads through it too", (host_card_of(pc_host()) or {}).get("via") == "host")


@test
def test_the_logs_page_reads_through_the_host(ctx: Ctx):
    from halo_harness.ollama_steward.cli_logs import cmd_ollama_log
    with HostRig() as rig:
        rig.start()
        rig.pair()
        code, got = _api(rig, "GET", "local/host/pc/log", query={"n": "50"})
        texts = [r["text"] for r in got.get("lines") or []]
        ctx.check(f"the tail arrives with its groups, source via host, got {code} {got.get('source')!r}", code == 200
                  and got["source"].startswith("via host 127.0.0.1") and any("prompt=41104" in t for t in texts)
                  and {"fit", "truncation"} <= {r["group"] for r in got["lines"]})
        ctx.check("no prompt body crossed", not any("the secret plan" in t for t in texts))
        code, st = _api(rig, "GET", "local/host/pc/log/status")
        ctx.check(f"the status route: rung host, got {code} {st.get('rung')} {st.get('line')!r}", code == 200
                  and st["rung"] == "host" and "via host" in st["line"])
        code, models = _api(rig, "GET", "local/host/pc/log/models")
        row = next((r for r in models.get("models") or [] if r["model"] == BIG), {})
        ctx.check(f"the per-model rows read the host's events: verified load, the cut prompt, got {row}",
                  code == 200 and row.get("load", {}).get("state") == "verified" and row.get("truncations"))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_ollama_log(["--host", "pc", "-n", "5"])
        ctx.check(f"halo ollama log --host pc: the source line says via host, got {out.getvalue()!r}", rc == 0
                  and "# via host 127.0.0.1" in out.getvalue())


@test
def test_a_profile_verified_on_the_host_and_its_evidence(ctx: Ctx):
    from halo_harness.providers.fit_evidence import evidence
    from halo_harness.providers.ollama_capability import profile_for
    with HostRig() as rig:
        rig.start()
        ctx.check("unpaired: no profile here", profile_for(rig.peer, BIG, "pc") is None)
        rig.pair()
        p = profile_for(rig.peer, BIG, "pc") or {}
        ctx.check(f"paired: verified, from the host, under this machine's host name, got {p}", p.get("truth") == "verified"
                  and p.get("source") == "the host at 127.0.0.1" and p.get("host") == "pc" and p.get("tools") == "yes")
        ev = evidence(rig.peer, "pc", BIG)
        ctx.check(f"the fit evidence reads the host's load: verified, 66/66, got {ev}", ev["state"] == "verified"
                  and ev["layers"] == [66, 66] and ev["source"] == "the log")


@test
def test_a_host_that_does_not_answer(ctx: Ctx):
    from halo_harness.ollama_steward import host_client
    from halo_harness.ollama_steward.log_status import status
    with HostRig() as rig:
        rig.start()
        rig.pair()
        rig.svc.stop()
        rig.svc = None
        t0 = time.monotonic()
        st = status(rig.peer, pc_host())
        ctx.check(f"one line: did not answer, got {st['state']} {st['line']!r}", st["state"] == "unreadable"
                  and "did not answer" in st["line"])
        ctx.check(f"marked down: the next read is immediate, got {host_client._DOWN}", bool(host_client._DOWN))
        t1 = time.monotonic()
        status(rig.peer, pc_host())
        ctx.check(f"the second read asks nothing ({time.monotonic() - t1:.2f}s after {t1 - t0:.2f}s)",
                  time.monotonic() - t1 < 0.5)
        from halo_harness.ollama_steward.log_status import ladder
        from halo_harness.providers.ollama import resolve_ollama_host
        rig.set_peer(**{"ollama.hosts": [{**PC, "ssh": "you@192.0.2.10"}]})
        ctx.check("with an ssh entry, a host that did not answer falls through to ssh (the ladder's next rung)",
                  ladder(rig.peer, resolve_ollama_host("pc"))["rung"] == "ssh")


@test
def test_probe_and_bench_through_a_host_say_r2(ctx: Ctx):
    with HostRig() as rig:
        rig.start()
        rig.pair()
        for act in ("probe", "bench", "load"):
            code, got = _api(rig, "POST", f"local/host/pc/{act}", body={"model": BIG})
            ctx.check(f"{act}: 409 naming the control grant (3.3.7.0 R2: a view peer), got {code} {got}", code == 409
                      and "need `control`" in got.get("error", "") and "halo host grant bob@peer control" in got["error"])
        code, hosts = _api(rig, "GET", "local/hosts")
        pc = next(h for h in hosts["hosts"] if h["name"] == "pc")
        ctx.check(f"the Hosts card: controls via host, the host block, got {pc['controls']} {pc.get('host')}",
                  pc["controls"]["via"] == "host" and not pc["controls"]["ok"] and pc["host"]["addr"] == "127.0.0.1"
                  and pc["host"]["started"] and pc["host"]["audit_count"] >= 1 and not pc["host"]["error"])


@test
def test_a_local_server_on_the_hosts_machine_reads_through_the_host(ctx: Ctx):
    """3.3.8.0 R2: `halo ollama hardware --host` lists that machine's servers; a peer's entry for one (its LAN url)
    reads its status and tail through the host, sizes only."""
    from halo_harness.ollama_steward.cli import cmd_ollama_hardware
    from halo_harness.ollama_steward.log_status_hf import status
    from halo_harness.ollama_steward.server_log_hf import tail_lines
    from halo_harness.ollama_steward.servers_hf import Server
    from tests.helpers.host_rig import host_server
    with HostRig() as rig:
        srv = host_server(rig.home)
        rig.readers["servers"] = lambda: [srv]
        rig.start()
        rig.pair()
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cmd_ollama_hardware(["--host", "pc"])
        ctx.check(f"the card lists the server via the host, got {out.getvalue()!r}", rc == 0
                  and "local server llama-8080: llama-server, qwen3-8b, window 8,192 per slot" in out.getvalue())
        mine = Server("box", "http://192.0.2.10:8080/v1", "llama-server")
        st = status(rig.peer, mine)
        ctx.check(f"the status: rung host, via host, got {st['rung']} {st['line']!r}", st["rung"] == "host"
                  and "via host 127.0.0.1" in st["line"])
        lines, source, why = tail_lines(mine, 20)
        ctx.check(f"the tail through the host, got {source} {why} {lines}", source.startswith("via host 127.0.0.1")
                  and any("input truncated" in x for x in lines) and not any("the secret plan" in x for x in lines))


@test
def test_the_hosts_local_servers_through_the_signed_api(ctx: Ctx):
    """3.3.8.0 R2: the card lists the machine's llama-server / LM Studio / mlx servers (runtime, model, window per
    slot, log status), `events` carries theirs, `tail?host=<server>` reads its log -- never a prompt body."""
    from tests.helpers.host_rig import host_server
    with HostRig() as rig:
        srv = host_server(rig.home)
        rig.readers["servers"] = lambda: [srv]
        rig.start()
        rig.pair()
        c = rig.client()
        rows = c.card().get("servers") or []
        ctx.check(f"the card's servers, got {rows}", len(rows) == 1 and rows[0]["name"] == "llama-8080"
                  and rows[0]["port"] == 8080 and rows[0]["runtime"] == "llama-server" and rows[0]["window"] == 8192
                  and rows[0]["model"] == "qwen3-8b" and rows[0]["log"]["readable"])
        evs = [e for e in c.events()["events"] if e.get("server")]
        ctx.check(f"its events, on its port, got {evs}", evs and evs[0]["host"] == "llama-8080" and evs[0]["port"] == 8080
                  and evs[0]["runtime"] == "llama-server")
        got = c.tail(50, host="llama-8080")
        text = " | ".join(got["lines"])
        ctx.check(f"its log, the body line replaced by its size, got {got}", got.get("server") and "input truncated" in text
                  and "the secret plan" not in text and "stays on this machine" in text)
        ctx.check("the Ollama tail is as before", "prompt=41104" in " | ".join(c.tail(50)["lines"]))

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
