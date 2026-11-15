"""halo_harness.local_ollama_cli -- Halo 3.6.0.0 R8: control a model on another machine from this one, with nothing
running there but Ollama. Every verb is Ollama's own API against an `ollama.hosts` entry (`/api/ps`,
`/api/generate` with `keep_alive`, `/api/pull`, `/api/show`); no Halo daemon and no pairing (`halo host` ops stay
for the people who run one).

    halo local ps [--host NAME] [--json]                           what is loaded where: its window, the card, how long
    halo local warm MODEL... [--host NAME] [--window N] [--keep 30m|forever] [--json]   load it now (a map name: its
                                                                   warm set, local_warm_cli.py)
    halo local unload MODEL|--all [--host NAME] [--json]           take it off the card now
    halo local pull MODEL [--host NAME] [--json]                   with progress; the size as soon as the server knows it
    halo local measure MODEL [--host NAME] [--again] [--json]      the ladder of loads: the largest window wholly on the
                                                                   card (asked for only; never from a turn)

Exit codes: 0 done (or nothing to do), 1 the server said no (a model it does not have, an error) or answered with
something that is not Ollama's answer (a sign-in page, a 401, a redirect: nothing is reported from it), 2 a usage
error (no such host, a bad argument), 3 the server did not answer. One plain line on a failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional

OK, REFUSED, USAGE, UNREACHABLE = 0, 1, 2, 3
EXIT_CODES = ("exit codes: 0 done (or nothing to do), 1 the server said no (a model it does not have, an error) or "
              "answered with something that is not Ollama's answer (a sign-in page, a redirect), 2 a usage error "
              "(no such host), 3 the server did not answer")
WARM_DEFAULT_WINDOW = 16384
_GB = 1024 ** 3


def _out(obj, as_json: bool, line: str, *, err: bool = False) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, default=str))
    elif line:
        print(line, file=sys.stderr if err else sys.stdout)


def _hosts(name: Optional[str]):
    """([hosts], error line): one named host, else (`ps`) every configured one."""
    from halo_harness.providers.ollama import resolve_ollama_host, resolve_ollama_hosts
    if name:
        h = resolve_ollama_host(name)
        if h is None:
            names = ", ".join(x.name for x in resolve_ollama_hosts()) or "none"
            return [], f"no Ollama host named {name!r} (configured: {names}; ollama.hosts in ~/.halo/config.json)"
        return [h], None
    return resolve_ollama_hosts(), None


def _one_host(name: Optional[str]):
    from halo_harness.providers.ollama import resolve_ollama_host
    if name:
        hosts, err = _hosts(name)
        return (hosts[0] if hosts else None), err
    h = resolve_ollama_host(None)
    return h, (None if h is not None else "no Ollama host configured (ollama.hosts in ~/.halo/config.json)")


def _gb(n) -> str:
    return f"{n / _GB:.1f} GB" if isinstance(n, (int, float)) and not isinstance(n, bool) else "?"


def _stays(expires) -> str:
    """'for ever' / 'about 4 min' / '?' from `/api/ps`'s `expires_at` (RFC 3339, nanoseconds and all)."""
    import datetime
    import re
    if not isinstance(expires, str) or not expires:
        return "?"
    s = re.sub(r"(\.\d{6})\d+", r"\1", expires.strip()).replace("Z", "+00:00")
    try:
        at = datetime.datetime.fromisoformat(s)
    except ValueError:
        return "?"
    if at.tzinfo is None:
        at = at.replace(tzinfo=datetime.timezone.utc)
    left = (at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    if left > 365 * 86400:
        return "for ever (until unloaded)"
    if left <= 0:
        return "leaving now"
    if left < 90:
        return f"about {int(left)} s"
    if left < 5400:
        return f"about {int(left / 60)} min"
    return f"about {left / 3600:.1f} h"


def ps_view(host) -> dict:
    """`{host, url, ok, reachable, say, models: [{model, window, size, size_vram, on_card, stays, expires}]}`."""
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked
    view = {"host": host.name, "url": host.url, "ok": False, "reachable": False, "models": [], "say": ""}
    why = control_blocked(host)
    if why:
        return {**view, "say": f"{host.name}: {why}"}
    reply = request_json(host, "/api/ps", timeout=10.0)
    from halo_harness.providers.ollama_load import came_back, is_ollama_answer
    if not is_ollama_answer(reply, "models") or not isinstance(reply.body.get("models"), list):
        if reply.failure in ("unreachable", "timeout", "error"):
            return {**view, "say": f"{host.name} ({host.url}) did not answer ({reply.failure})"}
        # 3.6.0.0 R8 fix pass M2/S8: it answered, and not as Ollama does -- nothing was read, nothing is reported
        return {**view, "reachable": True, "say": f"{host.name} ({host.url}) answered /api/ps with {came_back(reply)}: "
                                                  "not Ollama's answer, so nothing was read or changed"}
    rows = []
    for x in reply.body.get("models") or []:
        if not isinstance(x, dict):
            continue
        size, vram = x.get("size"), x.get("size_vram")
        on_card = ("all of it on the card" if isinstance(size, int) and isinstance(vram, int) and vram >= size
                   else f"{_gb(vram)} on the card, {_gb((size or 0) - (vram or 0))} on the CPU"
                   if isinstance(size, int) and isinstance(vram, int) else "?")
        rows.append({"model": x.get("model") or x.get("name"), "window": x.get("context_length"), "size": size,
                     "size_vram": vram, "on_card": on_card, "stays": _stays(x.get("expires_at")),
                     "expires": x.get("expires_at")})
    say = f"{host.name} ({host.url}): " + (f"{len(rows)} loaded" if rows else "nothing loaded")
    return {**view, "ok": True, "reachable": True, "models": rows, "say": say}


def _ps_lines(v: dict) -> list:
    lines = [v["say"]]
    for m in v["models"]:
        window = f"window {m['window']:,}" if isinstance(m.get("window"), int) else "window ?"
        lines.append(f"  {m['model']}  {window}  {_gb(m.get('size'))}, {m['on_card']}  stays {m['stays']}")
    return lines


def cmd_ps(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo local ps", epilog=EXIT_CODES, description=(
        "What is loaded on each Ollama server (or --host's): the model, the window it was loaded at, its memory "
        "and how much of it is on the card, and how long the server keeps it. One /api/ps read per server."))
    p.add_argument("--host", default=None, help="an ollama.hosts entry (default: every one)")
    p.add_argument("--json", action="store_true", help="the answer as JSON")
    args = p.parse_args(argv)
    hosts, err = _hosts(args.host)
    if err:
        _out({"ok": False, "say": err}, args.json, err, err=True)
        return USAGE
    views = [ps_view(h) for h in hosts]
    if args.json:
        print(json.dumps({"ok": all(v["ok"] for v in views), "hosts": views}, indent=2, default=str))
    else:
        for v in views:
            for line in _ps_lines(v):
                print(line)
    if any(not v["reachable"] for v in views):
        return UNREACHABLE
    return OK if all(v["ok"] for v in views) else REFUSED


# ---- warm ---------------------------------------------------------------------------------------------------------

def _keep(raw):
    """--keep: 'forever' (or -1) keeps it until unloaded; '30m' / '2h' / seconds as Ollama reads them; None: the
    server's own keep-alive."""
    if raw in (None, ""):
        return None
    if str(raw).strip().lower() in ("forever", "for-ever", "-1", "always"):
        return -1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return str(raw)


def warm_window(host, model: str, window: Optional[int]) -> "tuple[int, str]":
    """(the window to load at, where it came from): --window, else the steward profile's, else the window the last
    call on this host asked for, else 16,384 -- never above the host's max_ctx. A turn uses a loaded window that
    holds its request, so a warm load at any of these is not loaded again by the first turn."""
    from halo_harness.agent.ollama_window_truth import truth
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.ollama_load import window_for
    if isinstance(window, int) and window > 0:
        return window, "--window"
    got, where = window_for(host, model)
    if got and where == "the steward profile":
        return got, where
    last = truth(bridge_home(), host.url, model).get("num_ctx")
    if isinstance(last, int) and last > 0:
        return last, "the window the last call used"
    cap = host.max_ctx if isinstance(host.max_ctx, int) and host.max_ctx > 0 else None
    return (min(WARM_DEFAULT_WINDOW, cap) if cap else WARM_DEFAULT_WINDOW), "Halo's first-call window"


def warm(host, model: str, *, window: Optional[int] = None, keep=None) -> dict:
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.ollama_load import load
    num_ctx, where = warm_window(host, model, window)
    v = ps_view(host)
    if not v["ok"]:  # 3.6.0.0 R8 fix pass S8: no answer (3), or one that is not Ollama's (1)
        return {"ok": False, "code": UNREACHABLE if not v["reachable"] else REFUSED, "model": model, "say": v["say"]}
    here = next((m for m in v["models"] if ollama_names_match(m["model"], model)), None)
    if here is not None and keep is None and (window is None or here.get("window") == num_ctx):
        # loaded already: a turn uses the loaded window when it holds the request, so it is not loaded again
        at = f" at {here['window']:,}" if isinstance(here.get("window"), int) else ""
        return {"ok": True, "code": OK, "model": model, "window": here.get("window"), "already": True,
                "say": f"{model} is already loaded on {host.name}{at}: nothing to do"}
    t0 = time.monotonic()
    got = load(host, model, num_ctx=num_ctx, keep_alive=keep)
    took = round(time.monotonic() - t0, 1)
    if not got["ok"]:
        code = REFUSED if got.get("status") else UNREACHABLE
        say = (f"{host.name} does not have {model} (pull it: halo local pull {model} --host {host.name})"
               if got.get("status") == 404 else got["say"])
        return {"ok": False, "code": code, "model": model, "window": num_ctx, "say": say}
    kept = "kept until unloaded" if keep == -1 else (f"kept {keep}" if keep is not None
                                                     else "kept as long as the server keeps models")
    return {"ok": True, "code": OK, "model": model, "window": num_ctx, "window_from": where, "seconds": took,
            "keep_alive": keep, "say": f"{model} loaded on {host.name} at {num_ctx:,} ({where}) in {took:.1f} s, {kept}"}


def role_models() -> list:
    """Every `ol:` model the roles table and the default `model` name (the models `halo local warm` with no names
    warms; the host part of a ref is dropped: `--host` picks the server)."""
    from halo_harness.roles import configured_role_table
    from halo_harness.theme import get_config_value
    out: list = []
    for value in list(configured_role_table().values()) + [get_config_value("model", default=None)]:
        if isinstance(value, str) and value.startswith("ol:"):
            name = value[3:].split("@")[0]
            if name and name not in out:
                out.append(name)
    return out


def cmd_warm_models(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo local warm", epilog=EXIT_CODES + ". A map's name warms its warm set.",
                                description=(
        "Load a model on its server now, so the first turn does not wait for the load. The window: --window, else "
        "the steward profile's, else the window the last call used, else 16,384 (never above the host's max_ctx); "
        "a turn uses a loaded window that holds its request. Kept as long as the server keeps models unless --keep."))
    p.add_argument("models", nargs="+", help="the model(s), e.g. qwen3:8b")
    p.add_argument("--host", default=None, help="an ollama.hosts entry (default: the default host)")
    p.add_argument("--window", type=int, default=None, help="the window (num_ctx) to load at")
    p.add_argument("--keep", "--keep-alive", dest="keep", default=None,
                   help="how long the server keeps it: 30m, 2h, forever (default: the server's own setting)")
    p.add_argument("--json", action="store_true", help="the answer as JSON")
    args = p.parse_args(argv)
    host, err = _one_host(args.host)
    if err:
        _out({"ok": False, "say": err}, args.json, err, err=True)
        return USAGE
    rows = [warm(host, m, window=args.window, keep=_keep(args.keep)) for m in args.models]
    if args.json:
        print(json.dumps({"ok": all(r["ok"] for r in rows), "host": host.name, "models": rows}, indent=2, default=str))
    else:
        for r in rows:
            print(r["say"], file=sys.stdout if r["ok"] else sys.stderr)
    return max(r["code"] for r in rows)


# ---- unload -------------------------------------------------------------------------------------------------------

def cmd_unload(argv: list) -> int:
    from halo_harness.providers.ollama_load import unload
    p = argparse.ArgumentParser(prog="halo local unload", epilog=EXIT_CODES, description=(
        "Take a model off its server's card now (keep_alive 0). Halo never does this on its own: only this, Studio's "
        "Unload, a pivot you asked for, or a bundle you set up does."))
    p.add_argument("models", nargs="*", help="the model(s) to unload")
    p.add_argument("--all", action="store_true", help="every model loaded on the host")
    p.add_argument("--host", default=None, help="an ollama.hosts entry (default: the default host)")
    p.add_argument("--json", action="store_true", help="the answer as JSON")
    args = p.parse_args(argv)
    if not args.models and not args.all:
        p.print_usage(sys.stderr)
        print("halo local unload: name a model, or --all", file=sys.stderr)
        return USAGE
    host, err = _one_host(args.host)
    if err:
        _out({"ok": False, "say": err}, args.json, err, err=True)
        return USAGE
    v = ps_view(host)
    if not v["ok"]:  # 3.6.0.0 R8 fix pass M2: never "nothing is loaded" from an answer that was not Ollama's
        _out({"ok": False, "say": v["say"]}, args.json, v["say"], err=True)
        return UNREACHABLE if not v["reachable"] else REFUSED
    loaded = [m["model"] for m in v["models"]]
    from halo_harness.providers.ollama import ollama_names_match
    names = loaded if args.all else list(args.models)
    rows = []
    for name in names:
        if not any(ollama_names_match(name, m) for m in loaded):
            rows.append({"ok": True, "code": OK, "model": name, "say": f"{name} is not loaded on {host.name}: nothing to do"})
            continue
        got = unload(host, name)
        rows.append({"ok": got["ok"], "code": OK if got["ok"] else (REFUSED if got.get("status") else UNREACHABLE),
                     "model": name, "say": got["say"]})
    if not rows:
        rows.append({"ok": True, "code": OK, "model": None, "say": f"nothing is loaded on {host.name}"})
    if args.json:
        print(json.dumps({"ok": all(r["ok"] for r in rows), "host": host.name, "models": rows}, indent=2))
    else:
        for r in rows:
            print(r["say"], file=sys.stdout if r["ok"] else sys.stderr)
    return max(r["code"] for r in rows)


# ---- pull ---------------------------------------------------------------------------------------------------------

def cmd_pull(argv: list) -> int:
    import threading
    from halo_harness.models_control_cli import progress_line
    from halo_harness.providers.ollama_control import pull
    from halo_harness.studio.local_pull_job import _measure
    p = argparse.ArgumentParser(prog="halo local pull", epilog=EXIT_CODES + "; 130 cancelled (Ctrl+C: the server "
                                "keeps the layers it has)", description=(
        "Pull a model onto an Ollama server (it downloads there, not here), with progress. The size is said as "
        "soon as the server knows it."))
    p.add_argument("model", help="a library name (qwen3:8b) or hf.co/<repo>:<quant>")
    p.add_argument("--host", default=None, help="an ollama.hosts entry (default: the default host)")
    p.add_argument("--json", action="store_true", help="the answer as JSON")
    args = p.parse_args(argv)
    host, err = _one_host(args.host)
    if err:
        _out({"ok": False, "say": err}, args.json, err, err=True)
        return USAGE
    job = {"layers": {}, "samples": [], "status": "", "speed": None, "eta": None}
    said = {"size": False, "at": 0.0}
    cancel, box = threading.Event(), {}
    tty = sys.stdout.isatty() and not args.json

    def on(obj: dict) -> None:
        _measure(job, obj, time.monotonic())
        if not said["size"] and isinstance(job.get("total"), int) and job["total"] > 0 and not args.json:
            said["size"] = True
            print(f"pulling {args.model} on {host.name}: {_gb(job['total'])} to download")
        if tty:
            print("\r" + progress_line(job)[:110].ljust(110), end="", flush=True)
        elif not args.json and time.monotonic() - said["at"] > 5 and job.get("percent") is not None:
            said["at"] = time.monotonic()
            print(f"  {progress_line(job)}")

    if not args.json:
        print(f"asking {host.name} to pull {args.model} (the download runs there)")
    t = threading.Thread(target=lambda: box.update(pull(host, args.model, on_status=on, cancel=cancel)), daemon=True)
    t.start()
    while t.is_alive():
        try:
            t.join(0.2)
        except KeyboardInterrupt:
            cancel.set()
    if tty:
        print()
    got = {**box, "total": job.get("total"), "completed": job.get("completed")}
    if box.get("cancelled"):
        _out(got, args.json, box.get("say", ""), err=True)
        return 130
    if box.get("ok"):
        _out(got, args.json, f"{box['say']} ({_gb(job.get('total'))})" if job.get("total") else box["say"])
        return OK
    code = UNREACHABLE if box.get("error") == "unreachable" else REFUSED
    _out(got, args.json, box.get("say") or "the pull failed", err=True)
    return code


# ---- measure ------------------------------------------------------------------------------------------------------

def measure(host, model: str, *, again: bool = False, say=None, timeout: Optional[float] = None) -> dict:
    """The measurement E of the R8 brief: once per model digest and server version unless `again`; never above the
    host's max_ctx; the cold first load is a load; what was learned is kept even when a later step was slow."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.ollama import cached_ollama_version, get_catalog
    from halo_harness.providers.ollama_calibrate import (
        has_calibration_entry, lookup_learned_cap, lookup_tight, run_auto_calibration,
    )
    from halo_harness.providers.ollama_hw import catalog_row
    from halo_harness.providers.ollama_prompt import fmt_window
    say = say or (lambda s: None)
    v = ps_view(host)
    if not v["ok"]:
        return {"ok": False, "code": UNREACHABLE if not v["reachable"] else REFUSED, "say": v["say"]}
    row = catalog_row(get_catalog(host, force=True), model)
    if row is None:
        return {"ok": False, "code": REFUSED,
                "say": f"{host.name} does not have {model} (pull it: halo local pull {model} --host {host.name})"}
    state = bridge_home()
    version = cached_ollama_version(host)
    if not again and has_calibration_entry(state, host_url=host.url, model=model, digest=row.get("digest"),
                                           ollama_version=version):
        cap = lookup_learned_cap(state, host_url=host.url, model=model)
        tight = lookup_tight(state, host_url=host.url, model=model) or {}
        line = (f"{model} on {host.name}: measured already for this digest and Ollama {version or '?'} -- "
                + (f"{fmt_window(cap)} fits" if cap else "no window down to 4k fits")
                + (f", {fmt_window(tight['tight_ctx'])} tight" if tight.get("tight_ctx") else "")
                + " (--again measures it again)")
        return {"ok": True, "code": OK, "already": True, "max_full_gpu_ctx": cap, "say": line}
    cap = host.max_ctx if isinstance(host.max_ctx, int) and host.max_ctx > 0 else None
    say(f"measuring {model} on {host.name}: loads it at a few windows" + (f" up to {cap:,} (max_ctx)" if cap else "")
        + "; the first load is a cold one and gets its time")

    def _on_step(ctx, reading):
        what = {"safe": "wholly on the card", "tight": "on the card, tight", "offloaded": "part on the CPU"}.get(
            reading.kind, "no answer in its time (not counted as does-not-fit)")
        say(f"  {fmt_window(ctx)}: {what}")

    # 3.6.0.0 R8 fix pass S5: one measurement per server at a time (every process), the server left as it was found
    from halo_harness.providers.ollama_measure_guard import measuring
    with measuring(host, model, state) as guard:
        if not guard.ok:
            return {"ok": False, "code": REFUSED, "busy": True, "say": guard.say}
        line = run_auto_calibration(host, model, state_dir=state, timeout=timeout, on_step=_on_step)
    left = guard.left
    if left:
        say(left)
    if line is None:
        return {"ok": False, "code": REFUSED, "left": left,
                "say": f"the measurement of {model} on {host.name} failed" + (f"; {left}" if left else "")}
    learned = lookup_learned_cap(state, host_url=host.url, model=model, digest=row.get("digest"))
    ok = "no answer from the host" not in line
    return {"ok": ok, "code": OK if ok else UNREACHABLE, "max_full_gpu_ctx": learned, "left": left,
            "say": line + (f"; {left}" if left else "")}


def cmd_measure(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo local measure", epilog=EXIT_CODES, description=(
        "Measure the largest window that keeps a model wholly on its server's card: it loads the model at a few "
        "windows (each a full load: seconds to a minute each on a big model), never above the host's max_ctx, and "
        "records the answer for this model digest and Ollama version (run once; --again to repeat). No turn ever "
        "does this on its own."))
    p.add_argument("model", help="the model, e.g. qwen3:27b")
    p.add_argument("--host", default=None, help="an ollama.hosts entry (default: the default host)")
    p.add_argument("--again", action="store_true", help="measure again although this digest was measured")
    p.add_argument("--json", action="store_true", help="the answer as JSON")
    args = p.parse_args(argv)
    host, err = _one_host(args.host)
    if err:
        _out({"ok": False, "say": err}, args.json, err, err=True)
        return USAGE
    got = measure(host, args.model, again=args.again, say=None if args.json else print)
    _out(got, args.json, got["say"], err=not got["ok"])
    return got["code"]


COMMANDS = {"ps": cmd_ps, "unload": cmd_unload, "pull": cmd_pull, "measure": cmd_measure}
