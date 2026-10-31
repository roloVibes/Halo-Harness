"""halo_harness.host_steward_cli -- `halo host steward on --model REF | off | status | run` (Halo 3.3.7.0 R2;
docs/COMMANDS-host.md, docs/HOST.md "The duty steward").

The duty steward is an explicit opt-in, off by default (`host.steward.enabled` false): a **separate process**, never
the host process (H10.9: no model is ever in the host). `on` writes `host.steward.enabled: true` and
`host.steward.model`, gives the steward its own peer record on this host (the grants `--grant` names, `control` by
default), keeps its model's profile at a short keep_alive (`2m`, so the card is free soon after each pass and a warm
of another model evicts it: host/invariants.py), and starts `halo host steward run` detached (its pid in
`<state>/host/steward.json`). `run` is that process: a pass (host/duty.pass_once) every `host.steward.every_s` (300)
until `off` (the stop file) or the switch goes false. `off` stops it, drops its peer record and writes the switch
false. `status` says whether it runs, its model, its last note and what it holds on the card.
"""

from __future__ import annotations

import os
import sys
import time

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C

EVERY_S = 300.0
KEEP_ALIVE = "2m"
STOP_FILE = "steward-stop"
SEAMS: dict = {}  # "spawn": fn(argv) -> a Popen-like; "caller": the model call (the tests' seams)
USAGE = "usage: halo host steward on --model REF [--grant control|manage] | off | status | run [--once] [--json]"


def _parser(verb: str, description: str):
    import argparse
    p = argparse.ArgumentParser(prog=f"halo host steward {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def every_s(home) -> float:
    from halo_harness.host.state import _cfg
    try:
        v = float(_cfg("host.steward.every_s", EVERY_S, home))
    except (TypeError, ValueError):
        return EVERY_S
    return v if v > 0 else EVERY_S


def _stop_path(home):
    from halo_harness.host.state import host_dir
    return host_dir(home) / STOP_FILE


def _alive(pid) -> bool:
    from halo_harness.bg_run import pid_alive
    return isinstance(pid, int) and (pid == os.getpid() or pid_alive(pid))


def _key_of(model: str) -> "tuple[str, str]":
    from halo_harness.host.invariants import _bare
    from halo_harness.ollama_steward.profiles import key_for
    ref = str(model or "")
    host = ref.split("@", 1)[1] if "@" in ref else ""
    return key_for(host, _bare(ref)) if host else "", _bare(ref)


def cmd_on(argv: list) -> int:
    from halo_harness.host import duty
    from halo_harness.theme import set_config_value
    p = _parser("on", "Start the duty steward: a separate process running the steward on a small local model.")
    p.add_argument("--model", required=True, help="the steward's model ref (a small local one, e.g. ol:qwen3.5:9b@pc)")
    p.add_argument("--grant", default="control", choices=("control", "manage"), help="its grant on this host")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    home = identity.home()
    st = duty.read_state(home)
    if _alive(st.get("pid")) and st.get("pid") != os.getpid():
        return C.fail(a.json, "running", f"halo host steward on: it already runs (pid {st['pid']}, {st.get('model')})")
    set_config_value("host.steward.enabled", True)
    set_config_value("host.steward.model", a.model)
    identity.forget_cache()  # the host reads the switch through fleet/identity's one-second cache
    peer = duty.make_identity(home, ("view", a.grant))
    key, _m = _key_of(a.model)
    if key:
        from halo_harness.ollama_steward.agent_proposals import land_user
        land_user(home, {"key": key, "field": "keep_alive", "to": KEEP_ALIVE}, scope="keep", by="duty steward",
                  why="the duty steward's model: unloaded soon after each pass")
    try:
        _stop_path(home).unlink()
    except OSError:
        pass
    argv_ = [sys.executable, "-u", "-m", "halo_harness", "host", "steward", "run"]
    import subprocess
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kw["start_new_session"] = True
    try:
        proc = SEAMS["spawn"](argv_) if "spawn" in SEAMS else subprocess.Popen(argv_, **kw)
    except OSError as e:
        return C.fail(a.json, "not_started", f"halo host steward on: could not start it: {e}")
    duty.write_state(home, {"peer": peer, "pid": getattr(proc, "pid", None), "model": a.model, "grant": a.grant,
                            "started": time.time(), "every_s": every_s(home)})
    line = (f"the duty steward runs (pid {getattr(proc, 'pid', '?')}) on {a.model}: a separate process with its own "
            f"`{a.grant}` grant here, a pass every {int(every_s(home))} s, its model kept {KEEP_ALIVE} and evicted when "
            "the card is needed; `halo host steward off` stops it")
    if a.json:
        C.emit_json({"ok": True, "pid": getattr(proc, "pid", None), "model": a.model, "peer": peer, "line": line})
    else:
        print(line)
    return 0


def cmd_off(argv: list) -> int:
    from halo_harness.host import duty
    from halo_harness.theme import set_config_value
    a, rc = C.parse(_parser("off", "Stop the duty steward and drop its peer record."), argv)
    if a is None:
        return rc
    home = identity.home()
    st = duty.read_state(home)
    set_config_value("host.steward.enabled", False)
    identity.forget_cache()
    pid = st.get("pid")
    if _alive(pid) and pid != os.getpid():
        _stop_path(home).parent.mkdir(parents=True, exist_ok=True)
        _stop_path(home).write_text(str(time.time()), encoding="utf-8")
        end = time.time() + 10.0
        while time.time() < end and _alive(pid):
            time.sleep(0.2)
        if _alive(pid):
            import signal
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    duty.drop_identity(home)
    duty.drop_state(home)
    line = "the duty steward is off: no process, no peer record; the host is a monitor plus the grants you gave"
    if a.json:
        C.emit_json({"ok": True, "was_running": _alive(pid) or bool(pid), "line": line})
    else:
        print(line)
    return 0


def status(home) -> dict:
    from halo_harness.host import duty
    from halo_harness.host.state import _cfg
    from halo_harness.ollama_steward import notes
    st = duty.read_state(home)
    last = next((r for r in reversed(notes.read(home, stage="note")) if r.get("where") == "duty steward"), None)
    on = _cfg("host.steward.enabled", False, home) is True
    return {"enabled": on, "running": _alive(st.get("pid")), "pid": st.get("pid"), "model": _cfg("host.steward.model", None, home),
            "peer": st.get("peer"), "every_s": every_s(home), "last_note": (last or {}).get("say"),
            "last_at": (last or {}).get("at")}


def cmd_status(argv: list) -> int:
    a, rc = C.parse(_parser("status", "Is the duty steward on, its model, its last note."), argv)
    if a is None:
        return rc
    s = status(identity.home())
    if a.json:
        C.emit_json({"ok": True, **s})
        return 0
    if not s["enabled"]:
        print("the duty steward is off (halo host steward on --model REF starts it)")
        return 0
    print(f"the duty steward is on: {'running, pid ' + str(s['pid']) if s['running'] else 'not running'}; model "
          f"{s['model']}; a pass every {int(s['every_s'])} s; last note: {s['last_note'] or 'none yet'}")
    return 0


def cmd_run(argv: list) -> int:
    from halo_harness.host import duty
    from halo_harness.host.state import _cfg
    p = _parser("run", "The duty steward's own process (`on` starts it detached).")
    p.add_argument("--once", action="store_true", help="one pass, then exit")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    home = identity.home()
    while True:
        if _cfg("host.steward.enabled", False, home) is not True or _stop_path(home).exists():
            break
        got = duty.pass_once(home, _cfg("host.steward.model", None, home), caller=SEAMS.get("caller"))
        if a.once:
            if a.json:
                C.emit_json({"ok": True, **{k: v for k, v in got.items() if k != "note"}})
            return 0
        end = time.monotonic() + every_s(home)
        while time.monotonic() < end and not _stop_path(home).exists():
            time.sleep(1.0)
    try:
        _stop_path(home).unlink()
    except OSError:
        pass
    return 0


def cmd_steward(argv: list) -> int:
    verb, rest = (argv[0], argv[1:]) if argv else ("status", [])
    if verb in ("-h", "--help"):
        print(USAGE)
        return 0
    fn = {"on": cmd_on, "off": cmd_off, "status": cmd_status, "run": cmd_run}.get(verb)
    if fn is None:
        print(USAGE, file=sys.stderr)
        return 2
    return fn(rest)
