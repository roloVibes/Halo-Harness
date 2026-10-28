"""tests.test_settings_api -- Studio's Settings routes (Halo 3.3.3.0 R2, studio/settings_api.py,
studio/settings_values.py) through `api.dispatch` over a scratch home; no model call, no network:

1. `GET settings/catalog`: the groups and every row, each with its page and effect words;
2. `GET settings/values`: a value per row against its default, `set` false on a fresh home; a secret row and a
   secret-shaped value are masked, never in the answer;
3. `POST settings/set`: a bool, an int (a numeric string too), an enum, a list, a mapping, a keyed entry
   (`connectors.<slug>.enabled`, `ollama.hosts[<name>].ssh`) land in config.json, the answer says the effect;
4. 422 with `problems` and config.json unchanged: a bad kind, a bad choice, an unknown key, a removed key
   (`halo config set`'s words), a theme name `halo config set` turns away, a mapping that is not JSON;
5. `POST settings/unset`: the key gone (a section it empties too), the default comes back;
6. methods and unknown paths.
Run: python -m tests.test_settings_api
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "OPENAI_", "TYPESAFE_", "EXPLABS_", "HF_", "HALO_SECRET_", "BRIDGE_STATE_DIR",
            "HALO_ENV_FILE", "BRIDGE_ENV_FILE")
SECRET = "sk-settings-test-0123456789abcdef"


class _Env:
    """A scratch home (BRIDGE_TEST_HOME) with every provider variable taken out of the environment and put back."""

    def __enter__(self):
        self._saved = {k: v for k, v in os.environ.items() if k.startswith(PREFIXES) or k == "BRIDGE_TEST_HOME"}
        for k in self._saved:
            os.environ.pop(k, None)
        d = Path(tempfile.mkdtemp(prefix="settings-api-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        from halo_harness.providers.config import default_state_dir
        self.state_dir, self.cwd = Path(default_state_dir()), d / "project"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cwd.mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        for k in [k for k in os.environ if k.startswith(PREFIXES) or k == "BRIDGE_TEST_HOME"]:
            os.environ.pop(k, None)
        os.environ.update(self._saved)

    def call(self, method: str, path: str, body=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=self.cwd, state_dir=self.state_dir))

    def config(self) -> dict:
        p = self.state_dir / "config.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


@test
def test_the_catalog_and_fresh_values(ctx: Ctx):
    from halo_harness.settings_catalog import rows
    with _Env() as e:
        status, cat = e.call("GET", "settings/catalog")
        ctx.check(f"200, got {status}", status == 200)
        ctx.check(f"the groups and every row, got {len(cat.get('rows', []))}", len(cat["rows"]) == len(rows()) and len(cat["groups"]) == 17)
        fe = next(r for r in cat["rows"] if r["key"] == "fleet.enabled")
        ctx.check(f"a row's shape, got {fe}", fe["kind"] == "bool" and fe["default"] is True and fe["page"] == "Settings -> Fleet"
                  and fe["effect"] == "next session" and fe["effect_words"] == "takes effect in the next session" and fe["help"])
        status, v = e.call("GET", "settings/values")
        vals = v["values"]
        ctx.check(f"a value per row, got {len(vals)}", status == 200 and set(vals) == {r.key for r in rows()})
        ctx.check("nothing is set on a fresh home", not any(x["set"] for x in vals.values() if "entries" not in x))
        ctx.check(f"the default beside the value, got {vals['fleet.share']}", vals["fleet.share"] == {
            "value": None, "set": False, "default": "events", "masked": False, "cli": "halo config set fleet.share events"})
        prov = vals["providers.<name>.enabled"]["entries"]
        ctx.check(f"a keyed row lists its known entries unset, got {[p['name'] for p in prov]}",
                  "openrouter" in [p["name"] for p in prov] and not any(p["set"] for p in prov))


@test
def test_masked_values_never_leave(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with _Env() as e:
        set_config_value("embeddings.api_key", SECRET)
        set_config_value("ollama.hosts", [{"name": "lan", "url": "http://192.0.2.10:11434", "api_key": SECRET}])
        status, v = e.call("GET", "settings/values")
        key = v["values"]["embeddings.api_key"]
        ctx.check(f"a secret row says set and masked, no value, got {key}", key["set"] and key["masked"] and key["value"] is None)
        hosts = v["values"]["ollama.hosts"]["value"]
        ctx.check(f"a secret-shaped field inside a list is redacted, got {hosts}", hosts[0]["api_key"] == "<redacted>" and hosts[0]["name"] == "lan")
        status, got = e.call("POST", "settings/set", {"key": "embeddings.api_key", "value": SECRET + "x"})
        ctx.check(f"a secret row saves and its answer has no value, got {status} {got.get('value')}", status == 200 and got["value"] is None)
        status, bad = e.call("POST", "settings/set", {"key": "embeddings.api_key", "value": 12})
        ctx.check(f"a secret row's problem never echoes the value, got {bad}", status == 422 and "12" not in json.dumps(bad))
        ctx.check("the key is in no answer", SECRET not in json.dumps([v, got, bad]))


@test
def test_set_by_kind(ctx: Ctx):
    with _Env() as e:
        for key, value, want in (("fleet.enabled", False, False), ("fleet.hub.port", "7431", 7431), ("fleet.share", "full", "full"),
                                 ("fleet.tags", ["gpu", "studio"], ["gpu", "studio"]), ("coach.probe.budget_factor", 2.5, 2.5),
                                 ("openai.dialect_overrides", '{"gpt-5": "responses"}', {"gpt-5": "responses"}),
                                 ("fleet.name", "  me@box  ", "me@box"), ("intro", "off", False)):
            status, got = e.call("POST", "settings/set", {"key": key, "value": value})
            ctx.check(f"{key}: 200 and the coerced value, got {status} {got.get('value')!r} {got.get('problems')}",
                      status == 200 and got["value"] == want and got["set"] is True)
            from halo_harness.studio.settings_values import walk
            ctx.check(f"{key}: config.json has {want!r}", walk(e.config(), key) == want)
        ctx.check(f"the answer says when it takes effect, got {got.get('line')!r}", got["line"] == "intro saved: takes effect on the next launch"
                  and got["effect"] == "next launch" and got["cli"] == "halo config set intro false")
        ctx.check("the siblings under fleet stay", e.config()["fleet"]["share"] == "full" and e.config()["fleet"]["hub"]["port"] == 7431)
        status, got = e.call("POST", "settings/set", {"key": "connectors.gmail.enabled", "value": False})
        ctx.check(f"a keyed entry, got {status} {got.get('entry', {}).get('entries')}", status == 200 and e.config()["connectors"]["gmail"] == {"enabled": False}
                  and got["entry"]["entries"] == [{"name": "gmail", "key": "connectors.gmail.enabled", "value": False, "set": True}])
        status, got = e.call("POST", "settings/set", {"key": "connectors", "value": {"gmail": {"enabled": True, "max_turns": 6}}})
        ctx.check(f"a keyed row's whole section from the JSON editor, got {status}", status == 200 and e.config()["connectors"]["gmail"]["max_turns"] == 6)
        e.call("POST", "settings/set", {"key": "ollama.hosts", "value": [{"name": "lan", "url": "http://192.0.2.10:11434"}]})
        status, got = e.call("POST", "settings/set", {"key": "ollama.hosts[lan].kv_cache_type", "value": "q8_0"})
        ctx.check(f"a field of a list entry by its name, got {status} {got.get('problems')}", status == 200
                  and e.config()["ollama"]["hosts"] == [{"name": "lan", "url": "http://192.0.2.10:11434", "kv_cache_type": "q8_0"}])


@test
def test_refusals_write_nothing(ctx: Ctx):
    with _Env() as e:
        e.call("POST", "settings/set", {"key": "fleet.share", "value": "status"})
        before = (e.state_dir / "config.json").read_bytes()
        cases = (({"key": "fleet.hub.port", "value": "lots"}, "fleet.hub.port: 'lots' is not a whole number"),
                 ({"key": "fleet.enabled", "value": "maybe"}, "fleet.enabled: 'maybe' is not true or false"),
                 ({"key": "fleet.share", "value": "everything"}, "fleet.share: 'everything' is not one of status, events, full"),
                 ({"key": "fleet.tags", "value": {"a": 1}}, "fleet.tags: {'a': 1} is not a list"),
                 ({"key": "openai.dialect_overrides", "value": "{not json"}, "openai.dialect_overrides: not valid JSON"),
                 ({"key": "no.such.key", "value": 1}, "no.such.key: not a config key Settings knows"),
                 ({"key": "theme_scene", "value": "x"}, "theme_scene: removed in 3.1.5.0 with the game themes, the key is ignored"),
                 ({"key": "theme", "value": "doom"}, "not a valid theme name: 'doom' (expected one of"),
                 ({"key": "connectors.<slug>.enabled", "value": True}, "connectors.<slug>.enabled: name the entry"),
                 ({"key": "ollama.hosts[none].ssh", "value": "me@box"}, "ollama.hosts has no entries yet"),
                 ({"key": "fleet.name", "value": ""}, "fleet.name: needs a value"),
                 ({"value": 1}, "the body needs key"))
        for body, want in cases:
            status, got = e.call("POST", "settings/set", body)
            ctx.check(f"{body}: 422 with {want!r}, got {status} {got.get('problems')}",
                      status == 422 and got["problems"] and got["problems"][0].startswith(want) and got["error"] == got["problems"][0])
        ctx.check("config.json is byte for byte as it was", (e.state_dir / "config.json").read_bytes() == before)
        ctx.check("a theme the halo config set words also hint a removed game theme", "doom" in json.dumps(e.call("POST", "settings/set", {"key": "theme", "value": "doom"})[1]))


@test
def test_unset_brings_the_default_back(ctx: Ctx):
    with _Env() as e:
        e.call("POST", "settings/set", {"key": "fleet.enabled", "value": False})
        e.call("POST", "settings/set", {"key": "model", "value": "or:mock/alpha"})
        status, got = e.call("POST", "settings/unset", {"key": "fleet.enabled"})
        ctx.check(f"200, set false, the default back, got {status} {got}", status == 200 and got["set"] is False and got["default"] is True
                  and got["line"] == "fleet.enabled back to its default: takes effect in the next session")
        ctx.check(f"the key and the section it emptied are gone, got {e.config()}", e.config() == {"model": "or:mock/alpha"})
        status, v = e.call("GET", "settings/values")
        ctx.check("the values say unset", v["values"]["fleet.enabled"]["set"] is False)
        status, got = e.call("POST", "settings/unset", {"key": "fleet.enabled"})
        ctx.check("an unset key unsets again", status == 200 and got["set"] is False)
        e.call("POST", "settings/set", {"key": "ollama.hosts", "value": [{"name": "lan", "url": "http://192.0.2.10:11434", "ssh": "me@box"}]})
        status, got = e.call("POST", "settings/unset", {"key": "ollama.hosts[lan].ssh"})
        ctx.check(f"a list entry's field goes, the entry stays, got {e.config().get('ollama')}", status == 200
                  and e.config()["ollama"]["hosts"] == [{"name": "lan", "url": "http://192.0.2.10:11434"}])
        status, got = e.call("POST", "settings/unset", {"key": "no.such.key"})
        ctx.check("an unknown key is a 422", status == 422)


@test
def test_methods_and_paths(ctx: Ctx):
    with _Env() as e:
        ctx.check("GET settings/set is a 405", e.call("GET", "settings/set")[0] == 405)
        ctx.check("POST settings/catalog is a 405", e.call("POST", "settings/catalog")[0] == 405)
        ctx.check("an unknown settings path is a 404", e.call("GET", "settings/nope")[0] == 404)
        from halo_harness.studio.api import _PREFIXES
        ctx.check("settings is its own prefix after setup (3.3.4.0 R5: ollama after it)", [p[0] for p in _PREFIXES][-3:] == ["setup", "settings", "ollama"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
