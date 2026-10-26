"""tests.test_ollama_discover -- Halo 3.2.3.0 R2: `providers.ollama_discover`
finds the Ollama servers on this machine's doors and, when asked, on the
network, merges a server reached twice into one row, marks the configured
ones, and `add_hosts` writes the chosen ones as `ollama.hosts` entries.

Hermetic: every server is a `tests/helpers/mock_ollama.MockUpstream` on
127.0.0.1:0; `ollama.discover.ports` names the mock ports, so the default
port (this box may run a real Ollama there) is never asked. The network
sweep runs in exactly one test, over a loopback CIDR with a 3 s cap.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST",
              "OLLAMA_API_KEY", "HALO_OFFLINE")
OTHER_TAGS = {"models": [{"name": "llama3.2:3b", "model": "llama3.2:3b", "size": 2000, "digest": "sha256:feed1",
                          "details": {"family": "llama"}}]}


class _Env:
    """A fresh home + state dir, the test seam on, two mock servers."""

    def __enter__(self):
        from halo_harness.providers.ollama_discover import reset_discover_cache
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-discover-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        for k in ("OLLAMA_HOST", "OLLAMA_API_KEY", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        reset_discover_cache()
        self.a = MockUpstream().start()
        self.b = MockUpstream(tags_response=OTHER_TAGS).start()
        from halo_harness.theme import set_config_value
        set_config_value("ollama.discover", {"ports": [self.a.port, self.b.port]})
        return self

    def __exit__(self, *exc):
        from halo_harness.providers.ollama_discover import reset_discover_cache
        self.a.stop()
        self.b.stop()
        reset_discover_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _hosts() -> list:
    from halo_harness.theme import get_config_value
    return get_config_value("ollama.hosts", default=None) or []


@test
def test_local_finds_both_mocks_with_their_models_and_marks_the_configured_one(ctx: Ctx):
    from halo_harness.providers.ollama_discover import discover
    from halo_harness.theme import set_config_value
    with _Env() as env:
        set_config_value("ollama.hosts", [{"name": "pc", "url": env.a.base_url, "default": True}])
        started = time.monotonic()
        rows = discover("local")
        took = time.monotonic() - started
        by_url = {r.url: r for r in rows}
        ctx.check(f"both mocks found, got {[r.url for r in rows]}",
                  set(by_url) == {env.a.base_url, env.b.base_url})
        a, b = by_url.get(env.a.base_url), by_url.get(env.b.base_url)
        ctx.check(f"a carries its models, got {a and a.models}", a is not None and a.models == ["qwen3:30b", "gpt-oss:20b"])
        ctx.check(f"b carries its models, got {b and b.models}", b is not None and b.models == ["llama3.2:3b"])
        ctx.check(f"a is configured under the entry's name, got {a}", a is not None and a.configured and a.name == "pc")
        ctx.check(f"b is new, named after its door and port, got {b}",
                  b is not None and not b.configured and b.name == f"local-{env.b.port}" and b.where == "loopback")
        ctx.check(f"version read from /api/version, got {b and b.version}", b is not None and b.version == "0.1.0-mock")
        ctx.check(f"the local pass stays within its budget, took {took:.1f} s", took < 5.0)
        d = b.as_dict() if b else {}
        ctx.check(f"the row shape, got {sorted(d)}",
                  sorted(d) == ["configured", "models", "name", "url", "version", "where"])


@test
def test_in_tests_only_the_configured_ports_are_asked(ctx: Ctx):
    from halo_harness.providers.ollama_discover import discover, discover_ports
    from halo_harness.theme import set_config_value
    with _Env():
        set_config_value("ollama.discover", {})
        ctx.check(f"no port without ollama.discover.ports in tests, got {discover_ports()}", discover_ports() == ())
        ctx.check("the real default otherwise", discover_ports(test_mode=False) == (11434,))
        rows = discover("local")
        ctx.check(f"nothing probed, got {list(rows)}", list(rows) == [])
        ctx.check(f"one note says why, got {rows.notes}", len(rows.notes) == 1 and "ollama.discover.ports" in rows.notes[0])


@test
def test_the_lan_scope_is_off_in_tests_with_one_note(ctx: Ctx):
    from halo_harness.providers.ollama_discover import TEST_LAN_NOTE, discover
    with _Env():
        rows = discover("lan")
        ctx.check(f"no rows, got {list(rows)}", list(rows) == [])
        ctx.check(f"exactly the one note, got {rows.notes}", rows.notes == [TEST_LAN_NOTE])
        both = discover("all")
        ctx.check(f"'all' keeps the local rows and the note, got {len(both)} {both.notes}",
                  len(both) == 2 and TEST_LAN_NOTE in both.notes)


@test
def test_the_sweep_over_a_loopback_cidr_finds_the_mocks(ctx: Ctx):
    """The one test with the seam off: the network pass sweeps 127.0.0.0/30
    on the mock ports only (this machine's own /24 is left out, the LAN
    address is pinned to loopback, reverse DNS is stubbed), a 3 s cap."""
    from halo_harness.fleet import hub
    from halo_harness.providers import ollama_discover_net as net
    from halo_harness.providers.ollama_discover import discover
    from halo_harness.theme import set_config_value
    with _Env() as env:
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        saved = hub.lan_address, net.reverse_name
        hub.lan_address = lambda: "127.0.0.1"
        net.reverse_name = lambda ip, timeout=1.0: None
        try:
            set_config_value("ollama.discover", {"ports": [env.a.port, env.b.port],
                                                 "subnets": ["127.0.0.0/30", "198.18.0.0/16"]})
            progress = []
            started = time.monotonic()
            rows = discover("lan", budget_s=3.0, own_subnet=False, on_progress=progress.append)
            took = time.monotonic() - started
        finally:
            hub.lan_address, net.reverse_name = saved
        urls = sorted(r.url for r in rows)
        ctx.check(f"both mocks answer the sweep, got {urls}", urls == sorted([env.a.base_url, env.b.base_url]))
        ctx.check(f"each is a network row named after its last octet, got {[(r.where, r.name) for r in rows]}",
                  all(r.where == "lan" and r.name.startswith("ollama-1-") for r in rows))
        ctx.check(f"a /16 is skipped with one line, got {rows.notes}",
                  any("198.18.0.0/16" in n and "wider than a /24" in n for n in rows.notes))
        ctx.check(f"the progress line names the subnet, got {progress}", progress and "127.0.0.0/30" in progress[0])
        ctx.check(f"within the 3 s cap, took {took:.1f} s", took < 3.5)


@test
def test_one_server_on_two_doors_is_one_row_the_loopback_kept(ctx: Ctx):
    from halo_harness.providers.ollama_discover import Found, dedupe
    models, digests = ["qwen3:30b"], ("sha256:aa",)
    rows = [Found(url="http://192.0.2.7:11434", name="me", version="0.12.0", models=models, where="self",
                  digests=digests),
            Found(url="http://127.0.0.1:11434", name="local", version="0.12.0", models=models, digests=digests),
            Found(url="http://[::1]:11434", name="local", version="0.12.0", models=models, digests=digests),
            Found(url="http://192.0.2.7:11434", name="ollama-7", version="0.12.0", models=models, where="lan",
                  digests=digests),
            Found(url="http://192.0.2.9:11434", name="ollama-9", version="0.12.0", models=models, where="lan",
                  digests=digests),
            Found(url="http://192.0.2.10:11434", name="ollama-10", version="0.12.0", models=models, where="lan",
                  digests=digests)]
    kept = dedupe(rows)
    ctx.check(f"loopback first, the self door and the scan's own address merged into it, got "
              f"{[(r.where, r.url) for r in kept]}",
              [r.url for r in kept] == ["http://127.0.0.1:11434", "http://192.0.2.9:11434", "http://192.0.2.10:11434"])
    ctx.check("two network machines serving the same models stay two rows",
              sum(1 for r in kept if r.where == "lan") == 2)
    other_port = Found(url="http://127.0.0.1:11435", name="local-11435", version="0.12.0", models=models,
                       digests=digests)
    ctx.check("a second daemon on another port is its own row", len(dedupe([rows[1], other_port])) == 2)


@test
def test_add_hosts_writes_never_repoints_the_first_stays_default_no_duplicates(ctx: Ctx):
    from halo_harness.providers.ollama_discover import add_hosts, discover
    with _Env() as env:
        rows = discover("local")
        lines = add_hosts(rows)
        hosts = _hosts()
        ctx.check(f"one line per host added, got {lines}", len(lines) == 2 and all("added Ollama host" in ln for ln in lines))
        ctx.check(f"both written, got {hosts}", sorted(h["url"] for h in hosts) == sorted([env.a.base_url, env.b.base_url]))
        ctx.check(f"the first entry ever is the default, only it, got {hosts}",
                  hosts[0].get("default") is True and not any(h.get("default") for h in hosts[1:]))
        ctx.check(f"no key field written, got {hosts}",
                  all(set(h) <= {"name", "url", "default"} for h in hosts))
        again = add_hosts(discover("local"))
        ctx.check(f"a second add adds nothing, got {again} / {_hosts()}", again == [] and len(_hosts()) == 2)
        from halo_harness.providers.ollama_discover import Found
        from halo_harness.theme import set_config_value
        set_config_value("ollama.hosts", [{"name": "lab", "url": "http://192.0.2.50:11434", "default": True,
                                           "max_ctx": 8192}])
        clash = Found(url=env.b.base_url, name="lab", version="0.1.0-mock", models=["llama3.2:3b"])
        lines = add_hosts([clash])
        hosts = _hosts()
        ctx.check(f"the existing 'lab' is never repointed, got {hosts}",
                  hosts[0] == {"name": "lab", "url": "http://192.0.2.50:11434", "default": True, "max_ctx": 8192})
        ctx.check(f"the new one gets its own name, got {hosts[1:]} {lines}",
                  len(hosts) == 2 and hosts[1]["name"] == "lab-2" and "default" not in hosts[1])
        same_url = Found(url="http://192.0.2.50:11434", name="other", version="0.1.0-mock", models=[])
        ctx.check("a row at an existing host's address is left alone", add_hosts([same_url]) == [] and len(_hosts()) == 2)


@test
def test_add_hosts_named_rows_only_and_the_synthesized_default_kept_first(ctx: Ctx):
    from halo_harness.providers.ollama_discover import add_hosts, discover
    with _Env() as env:
        os.environ["OLLAMA_HOST"] = env.a.base_url  # the host Halo synthesizes with ollama.hosts empty
        rows = discover("local")
        a = next(r for r in rows if r.url == env.a.base_url)
        b = next(r for r in rows if r.url == env.b.base_url)
        ctx.check(f"the synthesized default counts as configured, got {a}", a.configured and a.name == "default")
        ctx.check("an unknown name adds nothing", add_hosts(rows, ["nope"]) == [] and _hosts() == [])
        lines = add_hosts(rows, [b.name])
        hosts = _hosts()
        ctx.check(f"the default is written first so ol:<model> keeps its daemon, got {hosts}",
                  [h["name"] for h in hosts] == ["default", b.name] and hosts[0]["default"] is True
                  and hosts[0]["url"] == env.a.base_url and "default" not in hosts[1])
        ctx.check(f"the lines say both, got {lines}", len(lines) == 2 and lines[0].startswith("kept the default"))


@test
def test_found_not_added_lines_and_the_detection_summary_list_both_mocks(ctx: Ctx):
    from halo_harness.providers.local_models import detection_summary_lines
    from halo_harness.providers.ollama_discover_hosts import found_not_added_lines, local_summary_lines
    from halo_harness.theme import set_config_value
    with _Env() as env:
        set_config_value("ollama.hosts", [{"name": "pc", "url": env.a.base_url, "default": True}])
        lines = found_not_added_lines(force=True)
        ctx.check(f"only b is found-not-added, got {lines}",
                  len(lines) == 1 and f"127.0.0.1:{env.b.port}" in lines[0]
                  and "found, not added (halo ollama discover --add)" in lines[0])
        summary = local_summary_lines()
        ctx.check(f"one summary line per local Ollama, got {summary}",
                  summary == [f"Ollama at 127.0.0.1:{env.a.port}: 2 models",
                              f"Ollama at 127.0.0.1:{env.b.port}: 1 model, not added"])
        detected = detection_summary_lines(env={})
        ctx.check(f"detection_summary_lines lists both mocks, got {detected}",
                  all(line in detected for line in summary))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
