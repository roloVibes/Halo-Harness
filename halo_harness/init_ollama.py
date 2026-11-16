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


_LISTED: list = []  # jb10: (ref, size) of every model the server picked this run listed; the final pick offers them


def listed_entries() -> "list[dict]":
    """The Ollama models this run's pick saw, as model_display entries (init_providers.model_entries_for_provider)."""
    return [{"ref": ref, "group": "ollama", **({"detail": size} if size else {})} for ref, size in _LISTED]


def _host_rows():
    """[(OllamaHost, is_new, label)]: this computer first unless it is a host already, then the hosts in config."""
    from halo_harness.providers.ollama import OllamaHost, resolve_ollama_hosts
    hosts = [h for h in resolve_ollama_hosts() if not h.synthesized]
    names = {h.name for h in hosts}
    local = _local_url()
    rows = []
    if not any(h.url.rstrip("/") == local.rstrip("/") for h in hosts):
        rows.append((OllamaHost(name=_free_name(names), url=local), True, f"this computer ({local})"))
    return rows + [(h, False, f"{h.name} ({h.url})") for h in hosts]


def _model_arg(args) -> "tuple[str, str]":
    """`--model` for the ollama row: (model name, host name or ''); `ol:` and `@<host>` are both optional."""
    raw = str(getattr(args, "model", None) or "").strip()
    raw = raw[3:] if raw.startswith("ol:") else raw
    name, at, host = raw.rpartition("@")
    return (name, host) if at else (raw, "")


def _pick_host(console, ask):
    """(OllamaHost, is_new) or None: a numbered list, never a typed address unless "another address" is chosen."""
    from halo_harness.providers.ollama import OllamaHost, _normalize_host_url
    rows = _host_rows()
    names = {h.name for h, new, _l in rows if not new}
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
    from halo_harness.init_cli import _non_interactive, _prompt_plain
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked
    console.print("[bold]Ollama[/bold] (no API key)")
    want, want_host = _model_arg(args)  # jb10: `--provider ollama --model <name>[@<host>]`
    quiet = _non_interactive(args)
    if want_host:
        found = [(h, new) for h, new, _l in _host_rows() if h.name == want_host]
        if not found:
            known = ", ".join(h.name for h, new, _l in _host_rows() if not new) or "none yet"
            console.print(f"   there is no Ollama host named {want_host!r} in ollama.hosts (known: {known}); "
                          "nothing was written")
            return None
        host, is_new = found[0]
    elif quiet:  # no terminal to ask on: the picker's default, row 1
        host, is_new = _host_rows()[0][:2]
    else:
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
    sizes = []
    for m in rows:
        details = m.get("details") if isinstance(m.get("details"), dict) else {}
        sizes.append(" ".join(str(details[k]) for k in ("parameter_size", "quantization_level") if details.get(k)))
    if want:
        if want not in names:
            console.print(f"   {want} is not on Ollama at {host.url}; it has: {', '.join(names)}")
            return None
        raw = str(names.index(want) + 1)
    elif quiet:
        console.print(f"   Ollama at {host.url} has: {', '.join(names)}. Nothing was written: pass one with --model, "
                      f"for example `halo init --provider ollama --model {names[0]}`")
        return None
    else:
        console.print(f"   Models on {host.name} ({host.url}):")
        for i, (name, size) in enumerate(zip(names, sizes), 1):
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
    _LISTED[:] = [(f"ol:{n}@{host.name}", s) for n, s in zip(names, sizes)]
    return ref, written, [], True
