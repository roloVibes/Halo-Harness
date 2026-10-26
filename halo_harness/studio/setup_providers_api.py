"""halo_harness.studio.setup_providers_api -- the Providers and Local models
routes of Studio's Setup section (Halo 3.3.0.0 R2; docs/STUDIO-setup.md).
Each one calls the writer the terminal wizard's Save calls, so a key lands in
the env file (`HALO_ENV_FILE`, else ~/.config/halo/env) through
`init_cli._write_env_var` and config.json keeps only variable names. A key
travels in the request body once (loopback, Studio's token) and is never in
an answer, a line or the state: the state says set, where from, ****1234.

    POST setup/provider/<name> {fields}       init_providers.save_tab_credentials, then
                                              enable_if_was_explicitly_disabled, reachability_tag,
                                              refresh_tab_catalog -> {...state, lines}
    POST setup/ollama-host {name, url, api_key?}   the Ollama tab's Save (the merge rule: a same-name
                                              save keeps the host's tuning, a blank save never
                                              repoints a host, the first host is the default)
    POST setup/ollama-host/remove {name}      the host leaves ollama.hosts; the first left is the default
    POST setup/hf {token} | {endpoint: {name, url, token?}} | {local_server: {name, url, api_key?}}
                  | {remove_endpoint: name} | {remove_local_server: name}
    POST setup/model-dir {path, remove?}      local_model_dirs.add_model_dir / forget_model_dir
    POST setup/runtime {runtime}              huggingface.preferred_runtime: llama-server | mlx_lm

A bad url or host is a 422 with `problems` and nothing written. Under
`BRIDGE_TEST_NO_BACKGROUND_NET=1` the test step probes nothing: reachable
"not checked", the catalog left as it is, one line saying so.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_PROVIDER = re.compile(r"^setup/provider/(?P<name>[a-z]+)$")
DBX_EXAMPLE = "https://your-workspace.cloud.databricks.com"


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _text(d, key: str) -> str:
    v = d.get(key) if isinstance(d, dict) else None
    return v.strip() if isinstance(v, str) else ""


def _refused(lines: list):
    return 422, {"error": lines[0] if lines else "not saved", "problems": list(lines)}


def _answer(req, lines: list):
    from halo_harness.studio.setup_state import setup_state
    return 200, {**setup_state(req.cwd, req.state_dir), "lines": list(lines)}


def url_problem(label: str, url: str) -> "str | None":
    """None for an http:// or https:// URL with a host name (a bare host:port is read as http://, the
    Ollama tab's rule); else one line."""
    raw = url if "://" in url else f"http://{url}"
    try:
        parsed = urlparse(raw)
        ok = parsed.scheme in ("http", "https") and bool(parsed.hostname) and not any(c.isspace() for c in url)
    except ValueError:
        ok = False
    return None if ok else f"{label}: {url!r} is not an http:// or https:// URL"


def with_scheme(url: str, scheme: str) -> str:
    """A URL typed without a scheme gets one: http:// for a local server, https:// for an endpoint."""
    return url if not url or "://" in url else f"{scheme}://{url}"


def probe_lines(name: str) -> "list[str]":
    """The wizard's test after a Save: the reachability probe, then the catalog refresh (one line each)."""
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.studio.setup_providers_state import LAST_REACH
    if background_net_disabled():
        LAST_REACH[name] = "not checked"
        return ["reachable: not checked · catalog not refreshed (no network in this run)"]
    from halo_harness.init_providers import refresh_tab_catalog
    from halo_harness.providers.reachability import reachability_tag
    tag = reachability_tag(name)
    reach = "ok" if tag == "reachable" else ("no" if tag.startswith("unreachable") else "not checked")
    LAST_REACH[name] = reach
    ok, note = refresh_tab_catalog(name)
    from halo_harness.config.paths import bridge_home
    from halo_harness.studio.setup_providers_state import _count
    n = _count(name, bridge_home())
    line = f"reachable: {reach}" + (f" ({tag.partition(': ')[2]})" if reach == "no" else "")
    line += f" · {n} model{'' if n == 1 else 's'} listed" if n else ""
    return [line] + ([f"catalog: {note}" if ok else f"catalog not refreshed: {note}"] if note else [])


def _saved(req, provider: str, values: dict):
    """save_tab_credentials -> 422 on its refusal; else enable the provider and run its test."""
    from halo_harness.init_providers import save_tab_credentials
    from halo_harness.providers.enablement import enable_if_was_explicitly_disabled
    ok, message = save_tab_credentials(provider, values)
    if not ok:
        return _refused([message])
    enable_if_was_explicitly_disabled(provider)
    return _answer(req, [message, *probe_lines(provider)])


def post_provider(req, name: str):
    from halo_harness.init_providers import TAB_PROVIDERS
    if name not in TAB_PROVIDERS:
        return 404, {"error": f"no provider named {name!r} (one of {', '.join(TAB_PROVIDERS)})"}
    raw = _body(req).get("fields")
    values = {str(k): v.strip() for k, v in raw.items() if isinstance(v, str)} if isinstance(raw, dict) else {}
    problems = []
    if name == "databricks" and not values.get("host") and values.get("token"):
        import os  # a token-only save keeps the host already set (the card shows it)
        values["host"] = (os.environ.get("DATABRICKS_HOST") or "").strip()
    if name == "databricks" and values.get("host"):
        from halo_harness.team_config import team_host_problem
        why = team_host_problem(values["host"])
        if why:
            problems.append(f"DATABRICKS_HOST: {why} (e.g. {DBX_EXAMPLE})")
    for key, label in (("url", "Ollama URL"), ("endpoint_url", "endpoint URL"), ("local_url", "local server URL")):
        if values.get(key):
            why = url_problem(label, values[key])
            if why:
                problems.append(why)
    if problems:
        return _refused(problems)
    if name == "huggingface":
        values.update(endpoint_url=with_scheme(values.get("endpoint_url", ""), "https"),
                      local_url=with_scheme(values.get("local_url", ""), "http"))
    return _saved(req, name, values)


def post_ollama_host(req):
    body = _body(req)
    url = _text(body, "url")
    why = url_problem("Ollama URL", url) if url else None
    if why:
        return _refused([why])
    return _saved(req, "ollama", {"name": _text(body, "name"), "url": url, "api_key": _text(body, "api_key")})


def post_ollama_remove(req):
    from halo_harness.studio.setup_providers_state import _config_list
    from halo_harness.theme import set_config_value
    name = _text(_body(req), "name")
    hosts = _config_list("ollama.hosts")
    gone = [h for h in hosts if (h.get("name") or h.get("url")) == name]
    if not name or not gone:
        return _refused([f"no Ollama host named {name!r} in ollama.hosts"])
    kept = [h for h in hosts if h not in gone]
    lines = [f"removed Ollama host {name!r} from ollama.hosts"]
    if kept and not any(h.get("default") for h in kept):
        kept[0] = {**kept[0], "default": True}
        lines.append(f"{kept[0].get('name') or kept[0].get('url')!r} is the default host now")
    set_config_value("ollama.hosts", kept)
    key_env = gone[0].get("api_key_env")
    if key_env:
        lines.append(f"its key stays in the env file as {key_env} (delete that line to forget it)")
    return _answer(req, lines)


def _remove_named(key: str, name: str, what: str, env_field: str):
    from halo_harness.studio.setup_providers_state import _config_list
    from halo_harness.theme import set_config_value
    rows = _config_list(key)
    kept = [r for r in rows if r.get("name") != name]
    if not name or len(kept) == len(rows):
        return None, [f"no {what} named {name!r} in {key}"]
    set_config_value(key, kept)
    lines = [f"removed {what} {name!r} from {key}"]
    env = next((r.get(env_field) for r in rows if r.get("name") == name and r.get(env_field)), None)
    if env:
        lines.append(f"its key stays in the env file as {env} (delete that line to forget it)")
    return lines, None


def post_hf(req):
    body = _body(req)
    for field, key, what, env_field in (("remove_endpoint", "huggingface.endpoints", "endpoint", "token_env"),
                                        ("remove_local_server", "huggingface.local_servers", "local server", "api_key_env")):
        if field in body:
            lines, problems = _remove_named(key, _text(body, field), what, env_field)
            return _refused(problems) if problems else _answer(req, lines)
    values, problems = {}, []
    if _text(body, "token"):
        values["token"] = _text(body, "token")
    ep = body.get("endpoint")
    if isinstance(ep, dict):
        if not _text(ep, "name") or not _text(ep, "url"):
            problems.append("an endpoint needs a name and a URL")
        elif url_problem("endpoint URL", _text(ep, "url")):
            problems.append(url_problem("endpoint URL", _text(ep, "url")))
        values.update(endpoint_name=_text(ep, "name"), endpoint_url=with_scheme(_text(ep, "url"), "https"), endpoint_token=_text(ep, "token"))
    ls = body.get("local_server")
    if isinstance(ls, dict):
        if not _text(ls, "url"):
            problems.append("a local server needs a URL")
        elif url_problem("local server URL", _text(ls, "url")):
            problems.append(url_problem("local server URL", _text(ls, "url")))
        values.update(local_name=_text(ls, "name"), local_url=with_scheme(_text(ls, "url"), "http"), local_key=_text(ls, "api_key"))
    if problems:
        return _refused(problems)
    return _saved(req, "huggingface", values)


def post_model_dir(req):
    from halo_harness.providers.local_model_dirs import add_model_dir, forget_model_dir
    from halo_harness.studio.setup_providers_state import forget_detection
    body = _body(req)
    path = _text(body, "path")
    if not path:
        return _refused(["the body needs path: a folder of .gguf files or model folders"])
    ok, message = (forget_model_dir if body.get("remove") else add_model_dir)(path)
    if not ok:
        return _refused([message])
    forget_detection()
    return _answer(req, [f"{message} (huggingface.model_dirs)"])


def post_runtime(req):
    from halo_harness.studio.setup_providers_state import RUNTIMES, forget_detection
    from halo_harness.theme import set_config_value
    runtime = _text(_body(req), "runtime")
    ids = [r[0] for r in RUNTIMES]
    if runtime not in ids:
        return _refused([f"runtime: {runtime!r} is not a runtime (one of {', '.join(ids)})"])
    path = set_config_value("huggingface.preferred_runtime", runtime)
    forget_detection()
    return _answer(req, [f"huggingface.preferred_runtime = {runtime} (saved to {path})"])


ROUTES = {"setup/ollama-host": post_ollama_host, "setup/ollama-host/remove": post_ollama_remove, "setup/hf": post_hf,
          "setup/model-dir": post_model_dir, "setup/runtime": post_runtime}


def dispatch_setup_providers(req):
    """The answer for one of these routes, or None when the path is not one of them."""
    m = _PROVIDER.match(req.path)
    fn = (lambda r: post_provider(r, m["name"])) if m else ROUTES.get(req.path)
    if fn is None:
        return None
    if req.method != "POST":
        return 405, {"error": "method not allowed"}
    try:
        return fn(req)
    except Exception as e:  # a config.json that does not parse is never written over: one line, no traceback
        return _refused([f"not saved: {type(e).__name__}: {e}"])
