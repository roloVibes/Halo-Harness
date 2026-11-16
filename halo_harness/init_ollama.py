"""halo_harness.init_ollama -- the terminal setup's Ollama row (`halo init --terminal`, and the console setup when
Studio cannot open): a person with local models only picks the server (this computer, a host already in
`ollama.hosts`, or another address), then one of the models that server lists (`/api/tags`, read with the same
`request_json` every Ollama reader uses), and the pick is saved as the default model the way Setup's Model page saves
it (`set_config_value("model", "ol:<name>@<host>")`; a new server joins `ollama.hosts` through Setup's own
`save_tab_credentials`). No API key is asked. A server that does not answer, or lists no model, is one line and the
provider list again; nothing is written until a model is picked.
"""
from __future__ import annotations

import os
from typing import Optional

ROW_LABEL = "ollama      no key      models on an Ollama server: this computer or one on your network"
READ_TIMEOUT_S = 5.0  # a short read: a server that does not answer never holds the setup up


def _local_url() -> str:
    """The Ollama on this computer: `OLLAMA_HOST` when set (as every Ollama client reads it), else 127.0.0.1:11434."""
    from halo_harness.providers.ollama import DEFAULT_OLLAMA_URL, _normalize_host_url
    return _normalize_host_url(os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_URL)


def _free_name(names: "set[str]") -> str:
    if not names:
        return "default"
    n, name = 1, "local"
    while name in names:
        n += 1
        name = f"local-{n}"
    return name


def _pick_host(console, ask):
    """(OllamaHost, is_new) or None: a numbered list, never a typed address unless "another address" is chosen."""
    from halo_harness.providers.ollama import OllamaHost, _normalize_host_url, resolve_ollama_hosts
    hosts = [h for h in resolve_ollama_hosts() if not h.synthesized]
    names = {h.name for h in hosts}
    local = _local_url()
    rows = []
    if not any(h.url.rstrip("/") == local.rstrip("/") for h in hosts):
        rows.append((OllamaHost(name=_free_name(names), url=local), True, f"this computer ({local})"))
    rows += [(h, False, f"{h.name} ({h.url})") for h in hosts]
    console.print("   Which Ollama?")
    for i, (_h, _new, label) in enumerate(rows, 1):
        console.print(f"     {i}. {label}")
    console.print(f"     {len(rows) + 1}. another address (you type it)")
    raw = ask(f"   choose [1-{len(rows) + 1}], default 1") or "1"
    idx = int(raw) if raw.isdigit() else 0
    if 1 <= idx <= len(rows):
        return rows[idx - 1][0], rows[idx - 1][1]
    if idx != len(rows) + 1:
        console.print("   no server picked; back to the provider list")
        return None
    from halo_harness.studio.setup_providers_api import url_problem
    url = ask("   Ollama URL (for example http://gpu-box:11434)")
    why = url_problem("Ollama URL", url) if url else "Ollama URL: nothing typed"
    if why:
        console.print(f"   {why}; back to the provider list")
        return None
    url = _normalize_host_url(url)
    from urllib.parse import urlparse
    guess = (urlparse(url).hostname or "lan").replace(".", "-")
    name = ask(f"   a short name for it (Enter: {guess})") or guess
    if name in names:
        console.print(f"   there is already an Ollama host named {name!r}: pick it from the list; back to the provider list")
        return None
    return OllamaHost(name=name, url=url), True


def _not_answered(reply, url: str) -> str:
    if reply.failure == "unreachable" and "connection refused" in (reply.error or ""):
        why = "nothing is listening there (connection refused)"
    elif reply.failure == "timeout":
        why = f"no answer within {READ_TIMEOUT_S:.0f}s"
    elif reply.failure in ("unreachable", "error"):
        why = "it could not be reached"
    else:
        from halo_harness.providers.ollama_load import came_back
        return (f"   Ollama at {url} did not answer as Ollama does ({came_back(reply)}): check the address; "
                "back to the provider list")
    return (f"   Ollama at {url} did not answer: {why}. Start Ollama there (`ollama serve`, or open the Ollama app), "
            "or install it from https://ollama.com; then pick ollama again.")


def run_ollama_setup(args, console) -> "Optional[tuple]":
    """`_run_provider_setup`'s shape for the ollama row: `(model_ref_raw, written, doctor_lines, pong_ok)` or None
    (one line already printed; back to the provider list)."""
    from halo_harness.init_cli import _prompt_plain
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked
    console.print("[bold]Ollama[/bold] (no API key)")
    picked = _pick_host(console, _prompt_plain)
    if picked is None:
        return None
    host, is_new = picked
    blocked = control_blocked(host)
    if blocked:
        console.print(f"   Ollama at {host.url}: {blocked}; back to the provider list")
        return None
    reply = request_json(host, "/api/tags", timeout=READ_TIMEOUT_S)
    models = reply.body.get("models") if reply.failure is None and isinstance(reply.body, dict) else None
    if not isinstance(models, list):
        console.print(_not_answered(reply, host.url))
        return None
    rows = [m for m in models if isinstance(m, dict) and (m.get("model") or m.get("name"))]
    names = [str(m.get("model") or m.get("name")) for m in rows]
    if not names:
        console.print(f"   Ollama at {host.url} has no models yet. Pull one with `halo local pull <model>` "
                      "(ollama.com/library lists them), then pick ollama again.")
        return None
    console.print(f"   Models on {host.name} ({host.url}):")
    for i, (name, m) in enumerate(zip(names, rows), 1):
        details = m.get("details") if isinstance(m.get("details"), dict) else {}
        size = " ".join(str(details[k]) for k in ("parameter_size", "quantization_level") if details.get(k))
        console.print(f"     {i}. {name}" + (f"   {size}" if size else ""))
    raw = _prompt_plain(f"   pick the default model [1-{len(names)}]")
    if not (raw.isdigit() and 1 <= int(raw) <= len(names)):
        console.print("   no model picked; back to the provider list")
        return None
    written = []
    if is_new:  # the server joins ollama.hosts the way Setup's Ollama tab adds one
        from halo_harness.init_providers import save_tab_credentials
        ok, line = save_tab_credentials("ollama", {"name": host.name, "url": host.url})
        console.print(f"   {line}")
        if not ok:
            return None
    from halo_harness.providers.enablement import enable_if_was_explicitly_disabled
    enable_if_was_explicitly_disabled("ollama")
    from halo_harness.theme import set_config_value
    ref = f"ol:{names[int(raw) - 1]}@{host.name}"
    path = set_config_value("model", ref)  # what Setup's Model page writes (setup_api.post_config)
    console.print(f"   Default model: {ref} -- wrote {path}")
    written.append(str(path))
    return ref, written, [], True
