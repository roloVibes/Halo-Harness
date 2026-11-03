"""halo_harness.strata.launch -- `halo local serve --runtime strata --model <family>/<set> [--port P] [--lan] [--plan]`
(or `--model-path DIR`) (Halo 3.3.9.2; docs/MODELS-strata.md "Serve"): Strata's `strata launch` through the managed-
runtime path.

    serve(model=None, *, model_path=None, port=None, lan=False, plan=False, state_dir=None, wait_s=None)
        -> (code, lines, row | None)   0 serving (or still starting in the background, or already serving that set,
        or the plan shown), 1 not started (no such set, another set runs, a name clash, the launch failed), 2 strata
        is missing or the first launch would download (the one line, the GB said)
    argv(prefix, row_or_path, *, port, lan) -> the `strata launch ...` command      entry() / forget() / key()
    write_entry(row) -> the `strata` entry of huggingface.local_servers from the registry row

The order (docs/TERMINAL_LAUNCH.md, docs/AI_SETUP.md; from the source, unverified against a live run): `strata launch
--plan --output json` first -- nothing is downloaded or changed -- and when its `download` says anything to fetch (the
set's tens to hundreds of GB, the engine for the card, the draft layer) Halo starts nothing and says the GB and the
command the user runs: the download is the user's, never Halo's. With nothing to fetch, `strata launch --family F
--model S --yes --no-tui --access local --port <free port> --api-key-env HALO_SECRET_STRATA_API_KEY` (Halo's key from
the env file, in the child's environment, never on a command line or in config.json; `--lan`: `--access lan`, every
address behind the key -- "Keep the server on 127.0.0.1 unless the user asks for more", AGENTS.md). Its output goes to
`<state>/local/servers/strata.log` after Halo's `--- halo starts:` line; the registry row `strata` (kind and runtime
strata, `keep`: Strata's supervisor runs the server, it outlives Halo) and the entry {name: strata, url, log, runtime,
model, strata: true, lan, api_key_env}. `/health` says `"service": "strata"` and `loaded` (serve/server.py); the wait is
WAIT_S, after which the start goes on in the background (said, never a failure); strata/control.settle reads the rest.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from halo_harness.strata import KEY_ENV, NAME, RUNTIME

POLL_S = 0.25
WAIT_S = 180.0
PLAN_S = 90.0


def _servers() -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.local_servers", default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def entry() -> Optional[dict]:
    return next((e for e in _servers() if str(e.get("name") or "").lower() == NAME), None)


def forget() -> bool:
    from halo_harness.theme import set_config_value
    rows = _servers()
    kept = [x for x in rows if not (str(x.get("name") or "").lower() == NAME and x.get("strata") is True)]
    if len(kept) != len(rows):
        set_config_value("huggingface.local_servers", kept)
    return len(kept) != len(rows)


def key(*, make: bool = False) -> Optional[str]:
    if os.environ.get(KEY_ENV):
        return os.environ[KEY_ENV]
    try:
        from halo_harness.providers.config import load_provider_env_files
        load_provider_env_files()
    except Exception:
        pass
    if os.environ.get(KEY_ENV) or not make:
        return os.environ.get(KEY_ENV) or None
    import secrets
    from halo_harness.init_cli import _env_file_path, _write_env_var
    k = secrets.token_urlsafe(24)
    _write_env_var(_env_file_path(), KEY_ENV, k)
    os.environ[KEY_ENV] = k
    return k


def _what(row: Optional[dict], model_path) -> list:
    return ["--model-path", str(model_path)] if model_path else ["--family", row["family"], "--model", row["set"]]


def argv(prefix: list, row: Optional[dict], *, port: int, lan: bool = False, model_path=None) -> list:
    return list(prefix) + ["launch"] + _what(row, model_path) + [
        "--yes", "--no-tui", "--access", "lan" if lan else "local", "--port", str(port), "--api-key-env", KEY_ENV]


def _plan(prefix, row, model_path, port, lan) -> "tuple[Optional[dict], str]":
    from halo_harness.strata.requirements import _run
    cmd = list(prefix) + ["launch"] + _what(row, model_path) + ["--plan", "--output", "json", "--port", str(port),
                                                                "--access", "lan" if lan else "local"]
    rc, out = _run(cmd, timeout=PLAN_S)
    try:
        got = json.loads(out.strip().splitlines()[-1]) if out.strip() else None
    except (ValueError, IndexError):
        got = None
    plan = got.get("plan") if isinstance(got, dict) else None
    return (plan if isinstance(plan, dict) else None), out.strip()


def _download_line(row: Optional[dict], plan: Optional[dict], model_path) -> Optional[str]:
    """The download the first launch would make, said with the GB; None when nothing is to fetch."""
    from halo_harness.strata.catalog import launch_words
    dl = (plan or {}).get("download") or {}
    gb = dl.get("gb") if isinstance(dl.get("gb"), (int, float)) else None
    engine = dl.get("engine_missing") is True
    if plan is not None and (gb or 0) < 0.05 and not engine:
        return None
    stated = row["download_gb"] if row and row.get("download_gb") else None
    words = (f"about {gb:.1f} GB ({dl.get('text') or 'the plan'})" if gb else
             f"about {stated:g} GB (Strata's table for {row['set']})" if stated else "the set (Strata states no size)")
    eng = "; the engine for this card comes with it" if engine else ""
    cmd = ("strata launch --model-path " + str(model_path) + " --yes --no-tui --access local") if model_path else launch_words(row)
    head = "the first launch downloads " if plan is not None else "strata launch --plan did not answer here: by "
    return (f"{head}{words}{eng} -- Strata's download, yours to run: {cmd}; then halo local serve --runtime strata again "
            "(or the auto-detect names it on its port)")


def serve(model: Optional[str] = None, *, model_path=None, port: Optional[int] = None, lan: bool = False,
          plan: bool = False, state_dir=None, wait_s: Optional[float] = None) -> "tuple[int, list, Optional[dict]]":
    from halo_harness.strata.catalog import parse
    from halo_harness.strata.requirements import check
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    row = parse(model) if model else None
    if model_path is None and row is None:
        return 1, [f"no Strata set named {model!r}: name it as <family>/<set> (qwen/IQ3_XXS, deepseek41/ist-das-2.00bpw; "
                   "halo models search strata lists them) or pass --model-path <the folder of its files>"], None
    if model_path is not None and not Path(str(model_path)).expanduser().exists():
        return 1, [f"no files at {model_path}: --model-path names a folder of shards or one .gguf"], None
    c = check()
    if not c["ok"]:
        gb = f"; its first launch downloads about {row['download_gb']:g} GB (Strata's table), yours to run" if (
            row and row.get("download_gb")) else ""
        return 2, [c["line"] + gb], None
    if plan:  # Strata's own answer and the fit here; nothing starts, nothing downloads
        from halo_harness.local_sched.fit_st import here_line
        from halo_harness.strata.requirements import _run
        rc, human = _run(list(c["strata"]) + ["launch"] + _what(row, model_path) + ["--plan"], timeout=PLAN_S)
        return (0 if rc == 0 else 1), [f"strata launch --plan ({c['strata_from']}), Strata's own answer:"] + [
            "  " + x for x in human.strip().splitlines()] + ([here_line(row, state_dir)] if row else []), None
    from halo_harness.providers import local_runtime as R
    from halo_harness.strata.control import alive
    running = next((e for e in R.load_registry(state_dir) if e.get("id") == NAME), None)
    want = Path(str(model_path)).name if model_path else f"{row['family']}/{row['set']}"
    if running is not None and alive(running):
        say = f"strata is running: {running.get('set') or running.get('model')} on http://127.0.0.1:{running.get('port')}"
        same = running.get("set") == want
        return (0, [say + ": already serving it"], running) if same else (1, [say + " -- halo local stop strata first"], None)
    clash = entry()
    if clash is not None and clash.get("strata") is not True:
        return 1, [f"huggingface.local_servers has an entry named {NAME!r} that Halo did not write: rename it first"], None
    port = int(port) if port else R.find_free_port()
    got, _text = _plan(c["strata"], row, model_path, port, lan)
    stop = _download_line(row, got, model_path)
    if stop:
        return 2, [stop], None
    return _start(c, row, model_path, want, port=port, lan=lan, state_dir=state_dir, wait_s=wait_s)


def _start(c: dict, row, model_path, want: str, *, port: int, lan: bool, state_dir, wait_s):
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers.local_server import servers_dir
    from halo_harness.strata.control import health, settle
    url = f"http://127.0.0.1:{port}"
    log = servers_dir(state_dir) / f"{NAME}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = argv(c["strata"], row, port=port, lan=lan, model_path=model_path)
    env = {**os.environ, KEY_ENV: key(make=True) or ""}
    lines = [f"strata {c['version']} from {c['strata_from']}" + (": every address, behind Halo's key" if lan else ""),
             "  " + " ".join(cmd)]
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(cmd)}\n".encode("utf-8"))
        out.flush()
        try:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        except OSError as e:
            return 1, lines + [f"strata launch did not start: {e}"], None
    R._register_popen(proc)
    owner_pid, owner_start = R._owner_fingerprint()
    from halo_harness.strata.catalog import set_name
    model = set_name(row) if row else want
    reg = {"id": NAME, "kind": RUNTIME, "runtime": RUNTIME, "model": model, "set": want, "model_path": str(model_path or ""),
           "pid": proc.pid, "port": port, "base_url": f"{url}/v1", "started": datetime.now(timezone.utc).isoformat(),
           "keep": True, "owner_pid": owner_pid, "owner_start": owner_start, "cmdline": list(cmd), "ready": False,
           "flags": {"lan": bool(lan), "family": (row or {}).get("family"), "set": (row or {}).get("set")},
           "sources": {"binary": c["strata_from"]}, "log": str(log), "launch_log": str(log), "halo": True}
    with R._registry_lock(state_dir):
        R.save_registry(state_dir, [e for e in R.load_registry(state_dir) if e.get("id") != NAME and e.get("port") != port]
                        + [reg])
    end = time.monotonic() + (wait_s if wait_s is not None else WAIT_S)
    while proc.poll() is None and time.monotonic() < end:
        time.sleep(POLL_S)
    if proc.poll() is None:
        write_entry(reg)
        from halo_harness.providers.local_server_cmd import tail_lines
        last = next((x.strip() for x in reversed(tail_lines(log, 12)) if x.strip()), "")
        return 0, lines + [f"{want} is still starting ({last[:120] or 'no line yet'}): it goes on in the background "
                           f"(halo local log {NAME} shows it)"], reg
    R._forget_popen(proc.pid)
    done = (settle(state_dir) or [reg])[0]
    if proc.returncode != 0 or not done.get("serving"):
        R.drop_registry_entries(state_dir, [(done.get("model"), done.get("pid"))])
        forget()
        from halo_harness.providers.local_server_cmd import tail_lines
        tail = [x for x in tail_lines(log, 8) if x.strip() and not x.startswith("--- halo starts:")]
        return 1, lines + [f"strata launch returned {proc.returncode} without serving:"] + [f"  {x}" for x in tail], None
    ready = health(port)["loaded"]
    lines.append(f"serving {done.get('model')} (Strata) on {url} -- use it as hf:local/{done.get('model')}@{NAME}" if ready
                 else f"{done.get('model')} is loading on {url}: halo local log {NAME} shows it")
    lines.append("  Strata keeps serving after Halo exits (its own supervisor runs it): halo local stop strata stops it")
    lines.append(f"  halo local log {NAME}   halo local stop {NAME}")
    return 0, lines, done


def write_entry(row: dict) -> None:
    from halo_harness.theme import set_config_value
    lan = bool((row.get("flags") or {}).get("lan"))
    e = {"name": NAME, "url": row["base_url"], "log": row["log"], "runtime": RUNTIME, "model": row["model"],
         "strata": True, "lan": lan, "api_key_env": KEY_ENV}
    set_config_value("huggingface.local_servers", [x for x in _servers() if str(x.get("name") or "").lower() != NAME] + [e])
