"""tests.test_setup_providers_api -- Setup's Providers and Local models routes
(Halo 3.3.0.0 R2, studio/setup_providers_api.py + setup_providers_state.py)
through `api.dispatch` over a scratch home with a fake env file (`HALO_ENV_FILE`
in it); no model call, no provider request (`BRIDGE_TEST_NO_BACKGROUND_NET=1`,
the one online case stubs the probe and the catalog). Pins: a key is written
once and is in no answer or state (set, from the env file, ****tail); the
Databricks https rule and the other 422s; the Ollama merge rule; Hugging Face's
token, endpoints and named local servers; model folders and the runtime; the
probe lines. Run: python -m tests.test_setup_providers_api
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.setup_home import SetupHome as _Env  # noqa: E402

test, TESTS = new_registry()
OR_KEY = "sk-or-v1-s2test-9f8e7d6c5b4a3210"
DBX_TOKEN = "dapi-s2test-0a1b2c3d4e5f6789"
OLLAMA_KEY = "olk-s2test-cloud-5566778899"
HF_TOKEN = "hf_s2testtoken_aabbccddeeff"


@test
def test_a_key_is_written_once_and_never_read_back(ctx: Ctx):
    with _Env() as e:
        from halo_harness.theme import set_config_value
        set_config_value("providers", {"openrouter": {"enabled": False}})
        status, s = e.call("GET", "setup/state")
        orp = s["providers"]["openrouter"]
        ctx.check(f"not set before, got {orp}", status == 200 and orp["set"] is False and orp["source"] == "not set" and orp["tail"] == "")
        ctx.check(f"its field: a secret, not present, got {orp['fields']}", orp["fields"] == [
            {"id": "key", "label": "OPENROUTER_API_KEY", "secret": True, "present": False, "placeholder": ""}])
        ctx.check(f"the eight cards with their labels, got {list(s['providers'])}",
                  len(s["providers"]) == 8 and s["providers"]["ollama"]["label"] == "Ollama (local or LAN)")
        ctx.check(f"the env file's path is in the state, got {s.get('env_file')!r}", s["env_file"] == str(e.env_file))
        status, s = e.call("POST", "setup/provider/openrouter", {"fields": {"key": "  " + OR_KEY + " "}})
        ctx.check(f"200, got {status} {s.get('lines')}", status == 200)
        ctx.check(f"the env file has the key, got {e.env_text()!r}", f"OPENROUTER_API_KEY={OR_KEY}" in e.env_text().splitlines())
        orp = s["providers"]["openrouter"]
        ctx.check(f"the state: set, from the env file, ****3210, enabled again, got {orp}",
                  orp["set"] and orp["source"] == "env file" and orp["tail"] == "****3210" and orp["enabled"] is True
                  and orp["fields"][0]["present"] is True)
        ctx.check("the explicit enabled: false was flipped (enable_if_was_explicitly_disabled)",
                  e.config()["providers"]["openrouter"]["enabled"] is True)
        ctx.check(f"the lines: what was written and the test, got {s['lines']}",
                  s["lines"][0] == f"wrote OPENROUTER_API_KEY to {e.env_file}" and s["lines"][1].startswith("reachable: not checked"))
        ctx.check("the key is in no answer", OR_KEY not in json.dumps(s) and "9f8e7d6c5b4a" not in json.dumps(s))
        _status, again = e.call("GET", "setup/state")
        ctx.check("and not in the state read again", OR_KEY not in json.dumps(again) and again["providers"]["openrouter"]["tail"] == "****3210")
        ctx.check("the status strip's names: openrouter set", [n for n, p in again["providers"].items() if p["set"]] == ["openrouter"])
        ctx.check("config.json holds no key", OR_KEY not in json.dumps(e.config()))


@test
def test_refusals_and_databricks(ctx: Ctx):
    with _Env() as e:
        status, body = e.call("POST", "setup/provider/databricks", {"fields": {"host": "http://your-workspace.cloud.databricks.com", "token": DBX_TOKEN}})
        ctx.check(f"an http host is a 422 with the https hint, got {status} {body.get('problems')}",
                  status == 422 and body["problems"] == ["DATABRICKS_HOST: the host must be an https:// URL (e.g. https://your-workspace.cloud.databricks.com)"])
        ctx.check("nothing written, the token not in the answer", not e.env_file.exists() and DBX_TOKEN not in json.dumps(body))
        status, body = e.call("POST", "setup/provider/databricks", {"fields": {"host": "https://your-workspace.cloud.databricks.com"}})
        ctx.check(f"no token: the wizard's line, got {status} {body.get('error')}", status == 422 and "DATABRICKS_TOKEN" in body["error"])
        status, body = e.call("POST", "setup/provider/anthropic", {"fields": {"key": "   "}})
        ctx.check(f"a blank key: 422, got {status} {body.get('error')}", status == 422 and body["error"] == "ANTHROPIC_API_KEY is needed")
        ctx.check("an unknown provider is a 404", e.call("POST", "setup/provider/nobody", {"fields": {}})[0] == 404)
        ctx.check("GET on a provider is a 405", e.call("GET", "setup/provider/openrouter")[0] == 405)
        status, body = e.call("POST", "setup/ollama-host", {"name": "lan", "url": "not a url"})
        ctx.check(f"a bad Ollama URL is a 422, got {status} {body.get('error')}", status == 422 and "Ollama URL" in body["error"])
        ctx.check("still nothing written", not e.env_file.exists() and "ollama" not in e.config())
        status, s = e.call("POST", "setup/provider/databricks", {"fields": {"host": "https://your-workspace.cloud.databricks.com", "token": DBX_TOKEN}})
        dbx = s["providers"]["databricks"]
        ctx.check(f"a good host + token: both in the env file, got {status} {e.env_text()!r}", status == 200
                  and "DATABRICKS_HOST=https://your-workspace.cloud.databricks.com" in e.env_text() and f"DATABRICKS_TOKEN={DBX_TOKEN}" in e.env_text())
        ctx.check(f"the card: set, the host shown, the token's tail, got {dbx}", dbx["set"] and dbx["detail"] == "https://your-workspace.cloud.databricks.com"
                  and dbx["tail"] == "****6789" and dbx["source"] == "env file" and DBX_TOKEN not in json.dumps(s))
        status, s = e.call("POST", "setup/provider/databricks", {"fields": {"token": DBX_TOKEN + "x"}})
        ctx.check(f"a token-only save keeps the host, got {status} {s.get('lines')}", status == 200 and f"DATABRICKS_TOKEN={DBX_TOKEN}x" in e.env_text()
                  and "DATABRICKS_HOST=https://your-workspace.cloud.databricks.com" in e.env_text() and s["providers"]["databricks"]["tail"] == "****789x")


@test
def test_ollama_hosts_follow_the_merge_rule(ctx: Ctx):
    with _Env() as e:  # documentation addresses only (192.0.2.x): nothing here is a real host
        status, s = e.call("POST", "setup/ollama-host", {})
        ctx.check(f"a blank save on no host registers the local daemon, got {s.get('ollama')}", status == 200
                  and s["ollama"]["hosts"] == [{"name": "default", "url": "http://127.0.0.1:11434", "default": True, "key_env": ""}])
        status, s = e.call("POST", "setup/ollama-host", {"name": "lan", "url": "192.0.2.10:11434"})
        hosts = s["ollama"]["hosts"]
        ctx.check(f"a second host, the first stays default, got {hosts}", status == 200 and [h["name"] for h in hosts] == ["default", "lan"]
                  and hosts[0]["default"] and not hosts[1]["default"] and hosts[1]["url"] == "http://192.0.2.10:11434")
        from halo_harness.theme import get_config_value, set_config_value
        set_config_value("ollama.hosts", [h if h["name"] != "lan" else {**h, "max_ctx": 32768} for h in get_config_value("ollama.hosts")])
        status, s = e.call("POST", "setup/ollama-host", {"name": "lan", "url": "192.0.2.11:11434"})
        raw = {h["name"]: h for h in e.config()["ollama"]["hosts"]}
        ctx.check(f"a repeat with the same name: updated, not doubled, its tuning kept, got {raw}", status == 200
                  and len(raw) == 2 and raw["lan"]["url"] == "http://192.0.2.11:11434" and raw["lan"]["max_ctx"] == 32768
                  and raw["default"]["default"] is True and s["lines"][0].startswith("updated Ollama host 'lan'"))
        status, s = e.call("POST", "setup/ollama-host", {"name": "cloud", "url": "https://ollama.com", "api_key": OLLAMA_KEY})
        cloud = [h for h in s["ollama"]["hosts"] if h["name"] == "cloud"][0]
        ctx.check(f"a key: its variable name in config.json, the value in the env file, got {cloud}",
                  cloud["key_env"] == "HALO_SECRET_OLLAMA_CLOUD" and f"HALO_SECRET_OLLAMA_CLOUD={OLLAMA_KEY}" in e.env_text()
                  and OLLAMA_KEY not in json.dumps(e.config()) and OLLAMA_KEY not in json.dumps(s))
        before = e.config()["ollama"]["hosts"]
        status, s = e.call("POST", "setup/ollama-host", {"name": "", "url": ""})
        ctx.check(f"a blank save over hosts changes nothing, got {s.get('lines')}", status == 200 and e.config()["ollama"]["hosts"] == before
                  and "nothing changed" in s["lines"][0])
        status, s = e.call("POST", "setup/ollama-host/remove", {"name": "default"})
        hosts = s["ollama"]["hosts"]
        ctx.check(f"removing the default: the first left is the default now, got {hosts} {s.get('lines')}", status == 200
                  and [h["name"] for h in hosts] == ["lan", "cloud"] and hosts[0]["default"] and "'lan' is the default host now" in s["lines"][1])
        status, s = e.call("POST", "setup/ollama-host/remove", {"name": "cloud"})
        ctx.check(f"removing a host with a key says where the key stays, got {s.get('lines')}", status == 200
                  and "HALO_SECRET_OLLAMA_CLOUD" in s["lines"][-1])
        ctx.check("an unknown host is a 422", e.call("POST", "setup/ollama-host/remove", {"name": "nope"})[0] == 422)
        status, s = e.call("POST", "setup/ollama-host/remove", {"name": "lan"})
        ctx.check(f"the last one removed: no hosts, got {s.get('ollama')} {e.config().get('ollama')}", status == 200
                  and s["ollama"]["hosts"] == [] and e.config()["ollama"]["hosts"] == [])


@test
def test_hugging_face_token_endpoints_and_servers(ctx: Ctx):
    with _Env() as e:
        status, s = e.call("POST", "setup/hf", {"token": HF_TOKEN})
        ctx.check(f"the token: HF_TOKEN in the env file, set, got {status} {s.get('huggingface')}", status == 200
                  and f"HF_TOKEN={HF_TOKEN}" in e.env_text() and s["huggingface"]["token_set"] and s["providers"]["huggingface"]["tail"] == "****eeff"
                  and HF_TOKEN not in json.dumps(s))
        status, body = e.call("POST", "setup/hf", {"endpoint": {"name": "mine"}})
        ctx.check(f"an endpoint without a URL is a 422, got {status} {body.get('error')}", status == 422 and body["error"] == "an endpoint needs a name and a URL")
        status, s = e.call("POST", "setup/hf", {"endpoint": {"name": "mine", "url": "abc.endpoints.huggingface.cloud", "token": "hf_ep_s2test_112233"}})
        ctx.check(f"an endpoint with a token, https added, got {s.get('huggingface', {}).get('endpoints')}", status == 200 and s["huggingface"]["endpoints"] == [
            {"name": "mine", "url": "https://abc.endpoints.huggingface.cloud", "token_env": "HALO_SECRET_HF_ENDPOINT_MINE"}]
                  and "hf_ep_s2test_112233" not in json.dumps(s) and "HALO_SECRET_HF_ENDPOINT_MINE=hf_ep_s2test_112233" in e.env_text())
        status, s = e.call("POST", "setup/hf", {"local_server": {"name": "gpu box", "url": "127.0.0.1:8080", "api_key": "lk-s2test-445566"}})
        ctx.check(f"a named local server, http added, its key a variable, got {s.get('huggingface', {}).get('local_servers')}", status == 200
                  and s["huggingface"]["local_servers"] == [{"name": "gpu box", "url": "http://127.0.0.1:8080", "key_env": "HALO_SECRET_HF_LOCAL_GPU_BOX"}]
                  and e.config()["huggingface"]["local_servers"][0]["default"] is True)
        status, s = e.call("POST", "setup/hf", {"local_server": {"url": "http://127.0.0.1:8081"}})
        ctx.check("a server with no name is the wizard's default entry", status == 200
                  and [x["name"] for x in s["huggingface"]["local_servers"]] == ["gpu box", "default"])
        status, s = e.call("POST", "setup/hf", {"remove_endpoint": "mine"})
        ctx.check(f"remove an endpoint, got {s.get('lines')}", status == 200 and s["huggingface"]["endpoints"] == []
                  and "HALO_SECRET_HF_ENDPOINT_MINE" in s["lines"][-1])
        status, s = e.call("POST", "setup/hf", {"remove_local_server": "gpu box"})
        ctx.check("remove a local server", status == 200 and [x["name"] for x in s["huggingface"]["local_servers"]] == ["default"])
        ctx.check("an unknown one is a 422", e.call("POST", "setup/hf", {"remove_local_server": "nope"})[0] == 422)
        ctx.check("an empty body is the wizard's 'nothing entered' 422", e.call("POST", "setup/hf", {})[0] == 422)


@test
def test_model_folders_and_the_runtime(ctx: Ctx):
    with _Env() as e:
        folder = e.home / "models"
        (folder / "one").mkdir(parents=True)
        (folder / "one" / "tiny.gguf").write_bytes(b"GGUF" + b"\0" * 64)
        status, s = e.call("GET", "setup/state")
        lm = s["local_models"]
        ctx.check(f"no folder, no runtime, the two runtimes, got {lm}", lm["model_dirs"] == [] and lm["runtime"] == ""
                  and [r["id"] for r in lm["runtimes"]] == ["llama-server", "mlx_lm"])
        ctx.check(f"detection probes nothing in this run, got {lm['detection']}", lm["detection"][0].endswith("(no network in this run)."))
        status, s = e.call("POST", "setup/model-dir", {"path": str(folder)})
        lm = s["local_models"]
        ctx.check(f"a folder added, got {status} {lm['model_dirs']} {s.get('lines')}", status == 200 and lm["model_dirs"] == [str(folder)]
                  and e.config()["huggingface"]["model_dirs"] == [str(folder)])
        ctx.check(f"the detection lines read again: the folder holds the model, got {lm['detection']}",
                  any(line == "The 1 model folder holds 1 model (gguf)." for line in lm["detection"]))
        ctx.check("the same folder again is a 422", e.call("POST", "setup/model-dir", {"path": str(folder)})[0] == 422)
        ctx.check("a missing folder is a 422", e.call("POST", "setup/model-dir", {"path": str(e.home / "nope")})[0] == 422)
        ctx.check("no path is a 422", e.call("POST", "setup/model-dir", {})[0] == 422)
        status, s = e.call("POST", "setup/model-dir", {"path": str(folder), "remove": True})
        ctx.check(f"removed, got {s.get('local_models', {}).get('model_dirs')}", status == 200 and s["local_models"]["model_dirs"] == [])
        status, s = e.call("POST", "setup/runtime", {"runtime": "mlx_lm"})
        ctx.check(f"the runtime saved, got {status} {s.get('lines')}", status == 200 and e.config()["huggingface"]["preferred_runtime"] == "mlx_lm"
                  and s["local_models"]["runtime"] == "mlx_lm")
        status, body = e.call("POST", "setup/runtime", {"runtime": "vllm"})
        ctx.check(f"another runtime is a 422, got {body.get('error')}", status == 422 and "llama-server" in body["error"])


@test
def test_the_probe_lines(ctx: Ctx):
    with _Env() as e:
        status, s = e.call("POST", "setup/provider/openai", {"fields": {"key": "sk-s2test-openai-77889900"}})
        ctx.check(f"no network: one line, reachable not checked, got {s.get('lines')}", status == 200
                  and s["lines"][1] == "reachable: not checked · catalog not refreshed (no network in this run)"
                  and s["providers"]["openai"]["reachable"] == "not checked")
        from halo_harness import init_providers
        from halo_harness.providers import reachability
        from halo_harness.studio import setup_providers_state as S
        real = (reachability.reachability_tag, init_providers.refresh_tab_catalog, S._count)
        calls = []
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        try:
            reachability.reachability_tag = lambda name, **_k: calls.append(("probe", name)) or "reachable"
            init_providers.refresh_tab_catalog = lambda name: calls.append(("catalog", name)) or (True, "312 model(s) cached")
            S._count = lambda name, _sd: 312 if name == "openai" else 0
            status, s = e.call("POST", "setup/provider/openai", {"fields": {"key": "sk-s2test-openai-77889901"}})
            ctx.check(f"the probe, then the catalog, got {calls}", calls == [("probe", "openai"), ("catalog", "openai")])
            ctx.check(f"the lines, got {s.get('lines')}", s["lines"][1:] == ["reachable: ok · 312 models listed", "catalog: 312 model(s) cached"])
            ctx.check("the card keeps what it found", s["providers"]["openai"]["reachable"] == "ok" and s["providers"]["openai"]["catalog_count"] == 312)
            reachability.reachability_tag = lambda name, **_k: "unreachable: connection refused"
            init_providers.refresh_tab_catalog = lambda name: (False, "URLError: refused")
            status, s = e.call("POST", "setup/provider/openai", {"fields": {"key": "sk-s2test-openai-77889902"}})
            ctx.check(f"unreachable: no, with the reason, got {s.get('lines')}", s["lines"][1] == "reachable: no (connection refused) · 312 models listed"
                      and s["lines"][2] == "catalog not refreshed: URLError: refused" and s["providers"]["openai"]["reachable"] == "no")
        finally:
            reachability.reachability_tag, init_providers.refresh_tab_catalog, S._count = real
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
