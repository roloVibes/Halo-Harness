"""halo_harness.studio.models_refresh -- Studio's Refresh of the model catalog
(Halo 3.1.4.0 R4; the owner: "I could never update it thus the drop down of
models never worked").

One job per provider a session would resolve (`catalog_env`): OpenRouter,
Anthropic, OpenAI, Hugging Face, Experiential Labs, Databricks, and each
`ollama.hosts` entry. They run in parallel, each inside one time box
(`BOX_S`, 6 seconds), and each says how it
went: `ok, <n> models`, or the one-line reason (no key, timed out, HTTP
<status> with what it means, unreachable: <why>). A job still running when
the box closes is named ("still asking"); when it answers later its line
replaces that one in the record. A provider with a key but turned off, or
detected but not enabled, gets its line too. Nothing is silent.

`refresh(state_dir, env)` returns and keeps `{at, box_s, outcomes}` in
<state>/studio/models-refresh.json; `last(state_dir)` reads it (GET
models/status shows it as "refreshed <when>"). `jobs_for` is the seam the
tests replace. Never raises; a key never reaches a line (`clean`).
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from pathlib import Path

BOX_S = 6.0
RECORD = "models-refresh.json"
_lock = threading.Lock()
_KEYISH = re.compile(r"(Bearer\s+)\S+|\b(?:sk|dapi|hf|xpl|key)[-_][A-Za-z0-9_-]{8,}", re.I)
_WHY = {401: "the key was refused", 403: "the key may not list models", 404: "no model list at that URL",
        429: "rate limited", 500: "the provider failed", 502: "a gateway in between failed", 503: "the provider is down"}


def clean(text) -> str:
    """One line, no key, at most 200 characters."""
    return _KEYISH.sub(lambda m: (m.group(1) or "") + "<redacted>", " ".join(str(text).split()))[:200]


def explain(e: BaseException) -> str:
    """The one-line reason a list did not come back."""
    m = re.search(r"returned (\d{3})", str(e))
    if m:
        code = int(m.group(1))
        return f"HTTP {code}" + (f" ({_WHY[code]})" if code in _WHY else "")
    text = clean(e)
    if isinstance(e, (socket.timeout, TimeoutError)) or "timed out" in text.lower():
        return "timed out" + (f": {text}" if text and "timed out" != text.lower() else "")
    from halo_harness.providers.http import UpstreamConnectError
    if isinstance(e, (UpstreamConnectError, OSError)):
        return "unreachable: " + text
    return f"{type(e).__name__}: {text}"


def _box() -> float:
    """The time box, seconds (`BOX_S`; the tests set it shorter)."""
    return float(BOX_S)


def _keyed(resolve, fetch, write, load):
    """A job for a provider with one key: resolve it, fetch the list (raises), write the cache, count it."""
    def job(state_dir, env):
        cfg = resolve(env)
        if cfg is None:
            return False, None, "on, but no key resolves (halo init, the keys step)"
        write(state_dir, fetch(cfg.base_url, cfg.api_key))
        return True, len(load(state_dir) or ()), ""
    return job


def _databricks(state_dir, env):
    from halo_harness.providers.databricks import load_dbx_endpoints_json, refresh_dbx_catalog_if_stale
    got = refresh_dbx_catalog_if_stale(state_dir, force=True, env=env)
    if got is None:
        return False, None, "on, but no workspace and token resolve (DATABRICKS_HOST / TOKEN, ~/.databrickscfg)"
    ok, _diff, note = got
    return (True, len(load_dbx_endpoints_json(state_dir) or ()), "") if ok else (False, None, clean(note) or "the list did not come back")


def _ollama(host):
    def job(state_dir, env):
        import urllib.error
        import urllib.parse
        import urllib.request
        from halo_harness.providers.http import urlopen_tls  # the one network choke point (offline mode, proxy, TLS)
        from halo_harness.providers.ollama import get_catalog, host_is_openai_dialect
        openai = host_is_openai_dialect(host)
        url = urllib.parse.urlparse(host.url)._replace(params="", query="", fragment="").geturl().rstrip("/")
        req = urllib.request.Request(url + ("/v1/models" if openai else "/api/tags"),
                                     headers={"Authorization": f"Bearer {host.api_key}"} if host.api_key else {})
        try:
            with urlopen_tls(req, timeout=_box()) as r:
                data = json.loads(r.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{host.name} returned {e.code}") from None
        except urllib.error.URLError as e:
            raise OSError(f"{url} ({e.reason})") from None
        n = len(data.get("data") or []) if openai else len(data.get("models") or [])
        try:
            get_catalog(host, force=True)  # the list GET models reads, fresh now
        except Exception:
            pass
        return True, n, ""
    return job


def jobs_for(state_dir, env, local: bool = True) -> list:
    """`[(name, provider, fn)]` for every provider to ask; `fn(state_dir, env)` -> (ok, count, line). A
    provider that is detected but not enabled, or turned off with a key present, has its line instead of a
    function. `local=False` leaves the Ollama hosts out."""
    from halo_harness.providers import anthropic_catalog as AC, config as C, databricks as D, experiential_catalog as XC
    from halo_harness.providers import huggingface_catalog as HC, openai_catalog as OC
    from halo_harness.providers.enablement import credentials_present, is_enabled, label_for
    keyed = [("openrouter", _keyed(C.resolve_openrouter, D.probe_openrouter_models, D.write_models_json, D.load_models_json)),
             ("anthropic", _keyed(C.resolve_anthropic, AC.fetch_anthropic_models, AC.write_ant_models_json, AC.load_ant_models_json)),
             ("openai", _keyed(C.resolve_openai, OC.probe_openai_models, OC.write_oai_models_json, OC.load_oai_models_json)),
             ("huggingface", _keyed(C.resolve_huggingface, HC.probe_huggingface_models, HC.write_hf_models_json, HC.load_hf_models_json)),
             ("experiential", _keyed(C.resolve_experiential, XC.probe_experiential_models, XC.write_xp_models_json, XC.load_xp_models_json)),
             ("databricks", _databricks)]
    out = []
    for provider, fn in keyed:
        detected = credentials_present(provider, env=env)
        if is_enabled(provider, detected=detected):
            out.append((label_for(provider), provider, fn))
        elif detected:
            out.append((label_for(provider), provider, f"a key is here but the provider is off: halo providers enable {provider}"))
    from halo_harness.providers.ollama import resolve_ollama_hosts
    for host in resolve_ollama_hosts(env) if local else ():
        out.append((f"Ollama ({host.name})", "ollama", _ollama(host)))
    return out


def _path(state_dir) -> Path:
    return Path(state_dir) / "studio" / RECORD


def _save(state_dir, record: dict) -> None:
    try:
        p = _path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def last(state_dir) -> "dict | None":
    try:
        data = json.loads(_path(state_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("outcomes"), list) else None
    except (OSError, ValueError):
        return None


def refresh(state_dir, env: dict, *, box_s: "float | None" = None, local: bool = True) -> dict:
    """Ask every provider at once; return (and keep) what each said within the box."""
    from halo_harness.packs.bio_models import forget
    forget()  # 3.2.0.0 R2: a bio's models.capabilities resolves against the new list
    box = float(box_s or _box())
    jobs = jobs_for(state_dir, env, local=local)
    results: dict = {}
    closed = threading.Event()

    def outcome(name, provider, ok, count, line, ms) -> dict:
        text = f"ok, {count} model{'' if count == 1 else 's'}" if ok else (line or "the list did not come back")
        return {"name": name, "provider": provider, "ok": bool(ok), "count": count if ok else None, "line": text, "ms": ms}

    def run(name, provider, fn) -> None:
        t0 = time.monotonic()
        try:
            ok, count, line = fn(state_dir, env)
        except Exception as e:  # one provider never takes the others down
            ok, count, line = False, None, explain(e)
        got = outcome(name, provider, ok, count, line, int((time.monotonic() - t0) * 1000))
        with _lock:
            results[name] = got
            if closed.is_set():  # it answered after the box: its line replaces "still asking"
                rec = last(state_dir)
                if rec:
                    rec["outcomes"] = [got if o.get("name") == name else o for o in rec["outcomes"]]
                    _save(state_dir, rec)

    threads = []
    for name, provider, fn in jobs:
        if callable(fn):
            t = threading.Thread(target=run, args=(name, provider, fn), daemon=True, name=f"halo-models-{provider}")
            t.start()
            threads.append(t)
        else:
            results[name] = {"name": name, "provider": provider, "ok": False, "count": None, "line": fn, "ms": 0, "skipped": True}
    deadline = time.monotonic() + box
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    with _lock:
        outcomes = [results.get(name) or {"name": name, "provider": provider, "ok": False, "count": None, "pending": True,
                                          "line": f"timed out after {box:g} s (still asking: its list lands when it answers)",
                                          "ms": int(box * 1000)} for name, provider, _fn in jobs]
        record = {"at": time.time(), "box_s": box, "outcomes": outcomes}
        _save(state_dir, record)
        closed.set()
    return record
