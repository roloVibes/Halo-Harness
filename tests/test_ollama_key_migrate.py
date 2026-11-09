"""tests.test_ollama_key_migrate -- Halo 3.3.13.1, the steward hotfix (e): an `ollama.hosts[]` entry holding its
key VALUE in `api_key` (providers/ollama_key_migrate.py). The first read of the hosts moves the value into the env
file (HALO_ENV_FILE, a scratch file here) under HALO_SECRET_OLLAMA_<NAME>, config.json keeps that name as
`api_key_env`, one stderr line names the host and the variable and never the value, and the key still reaches the
host; an env-var NAME in `api_key` is left alone; `halo doctor --config` has a `key-value` row while a value is there.
Fake values in a scratch home; 192.0.2.x addresses; nothing is sent anywhere.
Run: python -m tests.test_ollama_key_migrate
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FAKE = "fake-review-key-0123456789abcdef"
VAR = "HALO_SECRET_OLLAMA_LAN"
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "HALO_ENV_FILE", VAR)


class _Scratch:
    def __init__(self, hosts: list) -> None:
        self.hosts = hosts

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="keymig-")).resolve()
        self.state, self.env = self.root / ".halo", self.root / "scratch-env"
        self.state.mkdir(parents=True)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.state),
                          HALO_ENV_FILE=str(self.env))
        os.environ.pop(VAR, None)
        (self.state / "config.json").write_text(json.dumps({"ollama": {"hosts": self.hosts}}), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def config(self) -> dict:
        return json.loads((self.state / "config.json").read_text(encoding="utf-8"))


def _read_hosts() -> "tuple[list, str]":
    from halo_harness.providers.ollama import resolve_ollama_hosts
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        hosts = resolve_ollama_hosts()
    return hosts, err.getvalue()


@test
def test_a_key_value_moves_to_the_env_file_on_read(ctx: Ctx):
    with _Scratch([{"name": "lan", "url": "http://192.0.2.30:11434", "api_key": FAKE}]) as s:
        hosts, said = _read_hosts()
        entry = s.config()["ollama"]["hosts"][0]
        ctx.check(f"config.json names the variable and holds no value, got {entry}",
                  entry.get("api_key_env") == VAR and "api_key" not in entry and FAKE not in json.dumps(s.config()))
        ctx.check("the env file holds it", f"{VAR}={FAKE}" in s.env.read_text(encoding="utf-8"))
        ctx.check(f"one line, naming the host and the variable, never the value, got {said!r}",
                  said.count("\n") == 1 and "'lan'" in said and VAR in said and FAKE not in said)
        ctx.check("the host still sends the key", hosts[0].api_key == FAKE)
        hosts, said = _read_hosts()
        ctx.check(f"the next read is quiet and resolves the same, got {said!r}", said == "" and hosts[0].api_key == FAKE)


@test
def test_a_name_is_left_alone_and_a_copy_is_dropped(ctx: Ctx):
    from halo_harness.providers.ollama_key_migrate import looks_like_key
    ctx.check("a value looks like a key, a NAME does not", looks_like_key(FAKE) and not looks_like_key("MY_KEY_VAR")
              and not looks_like_key("") and not looks_like_key(None))
    with _Scratch([{"name": "lan", "url": "http://192.0.2.30:11434", "api_key": "MY_KEY_VAR"}]) as s:
        _hosts, said = _read_hosts()
        ctx.check(f"an UPPER_SNAKE name stays as it is, got {said!r}",
                  said == "" and s.config()["ollama"]["hosts"][0].get("api_key") == "MY_KEY_VAR")
    with _Scratch([{"name": "lan", "url": "http://192.0.2.30:11434", "api_key": FAKE, "api_key_env": VAR}]) as s:
        os.environ[VAR] = FAKE
        _hosts, said = _read_hosts()
        entry = s.config()["ollama"]["hosts"][0]
        ctx.check(f"a copy of what api_key_env already names is dropped, got {entry} {said!r}",
                  "api_key" not in entry and entry["api_key_env"] == VAR and "dropped the copy" in said
                  and not s.env.exists())


@test
def test_a_test_process_without_its_scratch_home_writes_nothing(ctx: Ctx):
    """The 3.3.13.1 fix pass saw a test module read the real ~/.halo (no test home in the runner's process); with
    the migration on read that became a write. Under the test flag with no scratch home, nothing is written."""
    from halo_harness import init_cli, theme
    from halo_harness.providers.ollama_key_migrate import migrate
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")}
    writes: list = []
    real = (theme.set_config_value, init_cli._write_env_var)
    theme.set_config_value = lambda *a, **k: writes.append(("config", a[0]))
    init_cli._write_env_var = lambda *a, **k: writes.append(("env", a[1]))
    try:
        os.environ.pop("BRIDGE_TEST_HOME", None)
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        hosts = [{"name": "lan", "url": "http://192.0.2.30:11434", "api_key": FAKE}]
        got = migrate(hosts, say=lambda _line: writes.append(("said", "")))
        ctx.check(f"nothing written or said, the hosts as they were, got {writes}", not writes and got is hosts)
    finally:
        theme.set_config_value, init_cli._write_env_var = real
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_doctor_config_names_a_key_value(ctx: Ctx):
    from halo_harness.doctor_config import finding
    from halo_harness.providers.ollama_key_migrate import key_findings
    row = {"file": "~/.halo/config.json", "path": "config.json", "kind": "config"}
    data = {"ollama": {"hosts": [{"name": "lan", "url": "http://192.0.2.30:11434", "api_key": FAKE},
                                 {"name": "cloud", "url": "http://192.0.2.31:11434", "api_key_env": VAR}]}}
    rows = key_findings(data, row, finding)
    ctx.check(f"one key-value row, the host named, the value never, got {rows}",
              len(rows) == 1 and rows[0]["check"] == "key-value" and "'lan'" in rows[0]["text"]
              and FAKE not in json.dumps(rows))
    with _Scratch([{"name": "lan", "url": "http://192.0.2.30:11434", "api_key": FAKE}]) as s:
        from halo_harness.doctor_config import config_findings
        found = config_findings(cwd=s.root, state_dir=s.state)
        ctx.check(f"halo doctor --config carries the row, got {[f['check'] for f in found]}",
                  any(f["check"] == "key-value" for f in found) and FAKE not in json.dumps(found, default=str))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
