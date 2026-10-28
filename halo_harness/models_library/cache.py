"""halo_harness.models_library.cache -- Halo 3.3.5.0 R2: the library's cache and its one fetch.

    path(state_dir)                     <state>/cache/models-library.json
    get(state_dir, key, ttl)            (value, at) when fresher than ttl, else None
    put(state_dir, key, value)          kept with its time; the oldest dropped past MAX_ENTRIES
    clear(state_dir)                    `halo models browse --refresh`, POST local/library/refresh
    fetch(url, headers=None) -> str     through providers/http.urlopen_tls (offline mode, the TLS policy); FetchError
    cached(state_dir, key, url, ttl, parse, refresh=False, headers=None) -> (value, at, "live" | "cache")
    offline()                           BRIDGE_TEST_NO_BACKGROUND_NET=1: the sources serve fixtures and the snapshot
    fixture(name)                       a file of FIXTURE_DIR (tests/fixtures/library in a checkout), or None

Ages: CATALOG_TTL_S (a day) for the Ollama catalog, a model's tags and a manifest; SEARCH_TTL_S (an hour) for a
hub search; a repo's files a day. `SEAMS["fetch"]` (url, headers) -> text is the tests' fake site.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

CACHE_NAME = "models-library.json"
CATALOG_TTL_S = 86400.0
SEARCH_TTL_S = 3600.0
REPO_TTL_S = 86400.0
MAX_ENTRIES = 400
TIMEOUT_S = 20
USER_AGENT = "halo-harness (models library browser)"
SEAMS: dict = {}
FIXTURE_DIR: Optional[Path] = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "library"
_LOCK = threading.Lock()


class FetchError(RuntimeError):
    """A page or an API answer that could not be read; the message says why in one line."""


def path(state_dir) -> Path:
    return Path(state_dir) / "cache" / CACHE_NAME


def offline() -> bool:
    from halo_harness.config.paths import background_net_disabled
    return background_net_disabled()


def fixture(name: str) -> Optional[str]:
    if FIXTURE_DIR is None:
        return None
    p = Path(FIXTURE_DIR) / name
    try:
        return p.read_text(encoding="utf-8") if p.is_file() else None
    except OSError:
        return None


def _read(state_dir) -> dict:
    try:
        data = json.loads(path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(state_dir, data: dict) -> None:
    p = path(state_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def get(state_dir, key: str, ttl: float, *, now: Optional[float] = None):
    if state_dir is None:
        return None
    with _LOCK:
        hit = _read(state_dir).get(key)
    if not isinstance(hit, dict) or not isinstance(hit.get("at"), (int, float)):
        return None
    now = time.time() if now is None else now
    return (hit.get("value"), hit["at"]) if now - hit["at"] < ttl else None


def put(state_dir, key: str, value, *, now: Optional[float] = None) -> float:
    at = time.time() if now is None else now
    if state_dir is None:
        return at
    with _LOCK:
        data = _read(state_dir)
        data[key] = {"at": at, "value": value}
        if len(data) > MAX_ENTRIES:
            for old in sorted(data, key=lambda k: (data[k] or {}).get("at") or 0)[: len(data) - MAX_ENTRIES]:
                data.pop(old, None)
        _write(state_dir, data)
    return at


def clear(state_dir) -> bool:
    with _LOCK:
        try:
            path(state_dir).unlink()
            return True
        except OSError:
            return False


def fetch(url: str, headers: Optional[dict] = None) -> str:
    """One GET through the one client; FetchError with a one-line reason on any failure."""
    seam: Optional[Callable] = SEAMS.get("fetch")
    if seam is not None:
        got = seam(url, dict(headers or {}))
        if got is None:
            raise FetchError(f"{url}: not found (404)")
        return got
    if offline():
        raise FetchError("background network reads are off (BRIDGE_TEST_NO_BACKGROUND_NET)")
    import urllib.error
    import urllib.request
    from halo_harness.providers.http import urlopen_tls
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urlopen_tls(req, timeout=TIMEOUT_S) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise FetchError(f"{url}: HTTP {e.code}") from None
    except Exception as e:  # DNS, TLS, timeouts, offline mode
        raise FetchError(f"{url}: {str(e) or type(e).__name__}") from None


def cached(state_dir, key: str, url: str, ttl: float, parse: Callable, *, refresh: bool = False,
           headers: Optional[dict] = None):
    """The parsed answer of `url`, from the cache when fresh; `parse(text)` may raise (a shape change)."""
    if not refresh:
        hit = get(state_dir, key, ttl)
        if hit is not None:
            return hit[0], hit[1], "cache"
    value = parse(fetch(url, headers))
    return value, put(state_dir, key, value), "live"
