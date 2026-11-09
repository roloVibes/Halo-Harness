"""halo_harness.engines.launch -- `halo local serve --runtime <engine id> --model M [--port P] [--keep] [--lan]
[--window N] [--parallel N]`: the descriptor's managed start, the way `halo local serve` runs llama-server.

    serve(engine, model, *, port=None, keep=False, lan=False, window=None, parallel=None, state_dir=None, wait_s=None)
        -> (code, lines, row | None)   0 serving (or still starting in the background, or already serving it), 1 not
        started (no such model, another model runs, a name clash, it exited), 2 the program or the model is missing,
        or the engine's own plan says its first start would download (the GB and the command said: the owner's)
    settle(state_dir, rows=None) -> [row]   a supervised engine whose start command returned: its log, its id, ready
The command is the descriptor's `start.argv`; Halo's key goes in the child's environment or a 0600 key file, never on
the command line or in config.json; the log is `<state>/local/servers/<id>.log`, the registry row and entry the id.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from halo_harness.engines import adapter as A
from halo_harness.engines.descriptors import get, install_line

POLL_S = 0.2


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _model(d: dict, model: str) -> "tuple[Optional[dict], int, str]":
    """What the start command is given: {path, model, name, model_head, model_tail}, or (None, code, the one line)."""
    kind, raw = d["start"]["model"], str(model or "").strip()
    p = Path(raw).expanduser()
    if kind in ("dir", "repo-or-dir") and p.is_dir():
        return {"path": str(p.resolve()), "model": str(p.resolve()), "name": p.name}, 0, ""
    if kind == "dir":
        return None, 1, (f"no checkpoint folder at {raw!r}: point --model at the folder that holds its config.json "
                         "(halo local download <repo> fetches one)")
    head, _, tail = raw.partition("/")
    if not (head and tail) or p.is_absolute():
        return None, 1, f"{d['label']} takes {'<family>/<set>' if kind == 'set' else 'a Hugging Face repo or a folder'}"
    if kind == "repo-or-dir":
        from halo_harness.providers.huggingface_hub_cache import resolve_hub_cache_root
        if not (resolve_hub_cache_root(None) / ("models--" + raw.split("@")[0].replace("/", "--"))).is_dir():
            from halo_harness.engines.models import match
            row = match(d["id"], raw)
            return None, 2, (f"{raw} is not in the Hugging Face cache: {(row or {}).get('pull') or 'download it'} "
                             "(yours to run), then serve it again")
    return {"path": raw, "model": raw, "name": tail.split("@")[0].rsplit("/", 1)[-1], "model_head": head,
            "model_tail": tail}, 0, ""


def _plan(d: dict, prefix: list, fields: dict) -> Optional[str]:
    """The engine's own dry run (Strata's `launch --plan`): the line to stop on when its first start downloads."""
    rc, out = A.run(list(prefix) + [a.format(**fields) for a in d["start"]["plan"]], timeout=90.0)
    try:
        plan = (json.loads(out.strip().splitlines()[-1]) or {}).get("plan") if rc == 0 and out.strip() else None
    except (ValueError, IndexError, AttributeError):
        plan = None
    dl = (plan or {}).get("download") or {}
    gb = dl.get("gb") if isinstance(dl.get("gb"), (int, float)) else 0.0
    if isinstance(plan, dict) and gb < 0.05 and dl.get("engine_missing") is not True:
        return None
    from halo_harness.engines.models import match
    row = match(d["id"], fields["model"]) or {}
    what = (f"about {gb:.1f} GB" if gb else f"about {row['size_gb']:g} GB (its table)" if row.get("size_gb") else
            "the set (no size stated)") + ("; the engine for this card with it" if dl.get("engine_missing") else "")
    return (f"{'the first start downloads' if plan else 'its plan did not answer; by its table it downloads'} {what} -- "
            f"the download is yours to run: {row.get('pull') or 'the engine itself'}; then serve it again")


def serve(engine: str, model: str, *, port: Optional[int] = None, keep: bool = False, lan: bool = False,
          window: Optional[int] = None, parallel: Optional[int] = None, state_dir=None,
          wait_s: Optional[float] = None) -> "tuple[int, list, Optional[dict]]":
    d, state_dir = get(engine), _state(state_dir)
    if not d.get("start"):
        return 1, [f"{d['label']} is detect-only: start it yourself and the auto-detect names it on its port"], None
    fields, code, why = _model(d, model)
    if fields is None:
        return code, [why], None
    prefix, src = A.binary(engine)
    v = A.version(engine, prefix) if prefix else None
    if v is None and not src.startswith("huggingface."):  # a configured program is taken as stated (the tests' fake)
        head = f"{'/'.join(d['programs'])} did not answer --version" if prefix else src or f"no {d['label']} program on PATH"
        return 2, [f"{head}: {install_line(d, A.os_word())} (it needs {d['requires']})"], None
    from halo_harness.providers import local_runtime as R
    running = next((e for e in R.load_registry(state_dir) if e.get("id") == engine), None)
    if running is not None and A.alive(running):
        say = f"{engine} is running: {running.get('model')} on http://127.0.0.1:{running.get('port')}"
        same = bool({fields["name"], fields["model"]} & {running.get("model"), running.get("set")})
        return (0, [say + ": already serving it"], running) if same else (1, [say + f" -- halo local stop {engine} first"], None)
    clash = A.entry(engine)
    if clash is not None and not A.ours(clash, engine):
        return 1, [f"huggingface.local_servers has an entry named {engine!r} that Halo did not write: rename it first"], None
    port = int(port) if port else R.find_free_port()
    fields.update(host="0.0.0.0" if lan else "127.0.0.1", access="lan" if lan else "local", port=port,
                  window=int(window or d["start"].get("window") or 32768), key_env=A.key_env(engine), parallel=parallel)
    if d["start"].get("plan") and (stop := _plan(d, prefix, fields)):
        return 2, [stop], None
    code, lines, row = _start(d, prefix, src, v, fields, keep=keep, lan=lan, state_dir=state_dir, wait_s=wait_s)
    if not (lan and code == 0 and row is not None):
        return code, lines, row
    from halo_harness.engines.launch_env import key_refused  # 3.3.14.0 R2 (REVIEW #24): announced only when true
    shut, why = key_refused(row["base_url"])
    if shut:
        return code, [lines[0] + f": every address, behind Halo's key ({why})"] + lines[1:], row
    A.stop_row(row, state_dir=state_dir)  # it does not check the key: it serves on loopback only, the row says why
    fields.update(host="127.0.0.1", access="local")
    code, more, row = _start(d, prefix, src, v, fields, keep=keep, lan=False, state_dir=state_dir, wait_s=wait_s)
    if row is not None:
        row["lan_off"] = f"--lan was not kept: {why}"
        _mark(state_dir, engine, lan_off=row["lan_off"])
    return code, [lines[0], f"  {d['label']} does not check Halo's key: {why}; it serves on 127.0.0.1 only"] + more[1:], row


def _start(d: dict, prefix: list, src: str, v, fields: dict, *, keep, lan, state_dir, wait_s):
    from halo_harness.bg_run import process_start_time
    from halo_harness.engines.launch_env import child_env, write_key
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    from halo_harness.providers.local_server import servers_dir
    engine, start, port = d["id"], d["start"], fields["port"]
    url = f"http://127.0.0.1:{port}"
    log = servers_dir(state_dir) / f"{engine}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = list(prefix) + [str(a).format(**fields) for a in start["argv"]]
    cmd += [str(a).format(**fields) for a in start.get("parallel") or ()] if fields.get("parallel") else []
    keyed = start.get("key") or {}
    # 3.3.14.0 R2 (REVIEW #22, LOCAL-2): the child gets a tool child's environment plus its own key, nothing more
    env = child_env(drop={A.key_env(engine), str(keyed.get("env") or "").format(**fields)})
    if keyed.get("env") and (lan or not keyed.get("lan_only")):
        env[keyed["env"].format(**fields)] = A.key(engine, make=True) or ""
    if keyed.get("file"):
        write_key(A.key_file(engine, state_dir), A.key(engine, make=True) or "")
        cmd += [keyed["file"], str(A.key_file(engine, state_dir))]
    env.update(start.get("env") or {})
    lines = [f"{d['label']} {v or ''} from {src}".replace("  ", " "), "  " + " ".join(cmd)]
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(cmd)}\n".encode("utf-8"))
        out.flush()
        try:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        except OSError as e:
            return 1, lines + [f"{d['label']} did not start: {e}"], None
    R._register_popen(proc)
    owner_pid, owner_start = R._owner_fingerprint()
    sup = bool(start.get("supervised"))
    reg = {"id": engine, "kind": engine, "runtime": engine, "model": fields["name"], "set": fields["model"],
           "model_path": fields["path"], "pid": proc.pid, "port": port, "base_url": f"{url}{d['base_path']}",
           "started": datetime.now(timezone.utc).isoformat(), "keep": bool(keep) or sup, "owner_pid": owner_pid,
           "owner_start": owner_start, "proc_start": process_start_time(proc.pid), "cmdline": list(cmd),
           "ready": False, "log": str(log), "launch_log": str(log),
           "flags": {"lan": bool(lan), "window": fields["window"], "parallel": fields.get("parallel")}, "halo": True}
    with R._registry_lock(state_dir):
        R.save_registry(state_dir, [e for e in R.load_registry(state_dir) if e.get("id") != engine and e.get("port") != port]
                        + [reg])
    end, ready = time.monotonic() + (wait_s if wait_s is not None else start.get("wait_s", 120.0)), False
    while time.monotonic() < end:
        if sup and proc.poll() is not None:
            break
        if not sup and (h := A.health(url))["ok"]:
            ready = h["ready"]
            if ready:
                break
        if not sup and proc.poll() is not None:
            break
        time.sleep(POLL_S)
    done = proc.poll()
    if (done is not None and not sup) or (sup and done not in (None, 0)):
        R.drop_registry_entries(state_dir, [(fields["name"], proc.pid)])
        R._forget_popen(proc.pid)
        tail = [x for x in C.tail_lines(log, 8) if x.strip() and not x.startswith("--- halo starts:")]
        return 1, lines + [f"{d['label']} exited ({done}) before it served:"] + [f"  {x}" for x in tail], None
    if sup and done == 0:
        R._forget_popen(proc.pid)
        reg = (settle(state_dir) or [reg])[0]
        ready = bool(reg.get("ready"))
    _mark(state_dir, engine, ready)
    reg["ready"] = ready
    A.write_entry(reg, lan)
    name = reg.get("model")
    lines.append(f"serving {name} ({d['label']}) on {url} -- use it as hf:local/{name}@{engine}" if ready else
                 f"{name} is still starting: it goes on in the background (halo local log {engine} shows it)")
    lines.append(f"  halo local log {engine}   halo local stop {engine}")
    if sup:
        lines.append(f"  {d['label']} keeps serving after Halo exits (its own supervisor runs it)")
    elif not keep:
        lines.append("  it stops when the last Halo process on this home exits (--keep keeps it running)")
    return 0, lines, reg


def _mark(state_dir, engine: str, ready: Optional[bool] = None, **fields) -> None:
    from halo_harness.providers import local_runtime as R
    with R._registry_lock(state_dir):
        rows = R.load_registry(state_dir)
        for e in rows:
            if e.get("id") == engine:
                e.update(fields, **({} if ready is None else {"ready": ready}))
        R.save_registry(state_dir, rows)


def _settled(e: dict) -> dict:
    import re
    d = get(e["kind"])
    start = d["start"]
    try:
        text = Path(e.get("launch_log") or e.get("log") or "").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    h = A.health(f"http://127.0.0.1:{int(e['port'])}") if e.get("port") else {"ok": False, "ready": False}
    found = re.findall(start["log_line"], text, re.M) if start.get("log_line") else []
    fields = {"pid": None, "settled": True, "ready": bool(h["ready"]), "serving": bool(h["ok"] or found)}
    if found:
        printed = Path(found[-1].strip()).expanduser()
        hit = next((r for r in A.status_rows(e["kind"], A.binary(e["kind"])[0]) or []
                    if str(r.get("port")) == str(e.get("port"))), None)
        srv = Path(start["server_log"].format(**{"profile": "", **hit, "log_dir": printed.parent})) if hit else None
        fields["log"] = str(srv.resolve()) if srv is not None and srv.is_file() else str(printed)
    if h["ok"]:
        from halo_harness.providers.huggingface_local_probe import _probe_get
        got = _probe_get(f"http://127.0.0.1:{int(e['port'])}/v1", "/models", api_key=A.key(e["kind"]), timeout=2.0)
        ids = [str(r["id"]) for r in (got or {}).get("data") or [] if isinstance(r, dict) and r.get("id")]
        fields["model"] = ids[0] if ids else e.get("model")
    return {**e, **fields}


def settle(state_dir, rows: Optional[list] = None) -> list:
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers import local_runtime as R
    rows = R.load_registry(state_dir) if rows is None else rows
    todo = [e for e in rows if ((get(e.get("kind")) or {}).get("start") or {}).get("supervised") and not e.get("settled")
            and not (isinstance(e.get("pid"), int) and pid_alive(e["pid"]))]
    out = [_settled(e) for e in todo]
    if not out:
        return []
    with R._registry_lock(state_dir):
        cur = R.load_registry(state_dir)
        for e in cur:
            hit = next((x for x in out if x.get("id") == e.get("id") and x.get("port") == e.get("port")), None)
            e.update(hit or {})
        R.save_registry(state_dir, cur)
    for e in out:
        if e.get("serving"):
            A.write_entry(e, bool((e.get("flags") or {}).get("lan")))
    return out
