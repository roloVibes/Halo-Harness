"""scripts/prepush_privacy.py -- the privacy steps of scripts/prepush.py (Halo 3.4.1.2, disclosure audit F8).

The audit runs in a scratch home (it must never read or write the real state), so before 3.4.1.2 it never saw the
owner's private term list (`<state dir>/privacy-terms.txt`) and every machine- and owner-name check was off in the
gate. Now the real list's PATH is found in this shell's own home and handed over in `HALO_PRIVACY_TERMS_FILE` (an
environment variable naming the file: no term on a command line, none copied); the scratch home stays.

    terms_file(env)          the real list, where `halo` itself would find it in this shell, or None
    audit_env(env, home)     the scratch-home environment for the audit, with HALO_PRIVACY_TERMS_FILE when there is a list
    name_line(path)          the one line the gate prints: name checks ON, or OFF and why (never silent)
    audit_steps(...)         `halo audit privacy` (the whole tree) and `halo audit privacy --commits`, as gate steps
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

TERMS_ENV = "HALO_PRIVACY_TERMS_FILE"


def terms_file(env: "dict | None" = None) -> "Path | None":
    env = os.environ if env is None else env
    if env.get(TERMS_ENV, "").strip():
        f = Path(env[TERMS_ENV].strip())
    elif env.get("BRIDGE_STATE_DIR", "").strip():
        f = Path(env["BRIDGE_STATE_DIR"]) / "privacy-terms.txt"
    else:
        f = Path(env.get("BRIDGE_TEST_HOME") or Path.home()) / ".halo" / "privacy-terms.txt"
    return f if f.is_file() else None


def audit_env(base: dict, home: str, terms: "Path | None") -> dict:
    env = dict(base)
    env.update(BRIDGE_TEST_HOME=home, HALO_HOME=home)
    env.pop("BRIDGE_STATE_DIR", None)
    env.pop(TERMS_ENV, None)
    if terms is not None:
        env[TERMS_ENV] = str(terms)
    return env


def name_line(terms: "Path | None", env: "dict | None" = None) -> str:
    env = os.environ if env is None else env
    if env.get("HALO_PRIVACY_TERMS", "").strip():
        return "prepush: privacy name checks ON (HALO_PRIVACY_TERMS from this shell)"
    if terms is not None:
        return "prepush: privacy name checks ON (the private term list in the state dir)"
    return ("prepush: privacy name checks OFF -- no private term list (<state dir>/privacy-terms.txt): machine and "
            "owner names are not checked")


def audit_steps(run_step, py: str, logdir: Path, base_env: dict) -> list:
    terms = terms_file()
    print(name_line(terms), flush=True)
    home = tempfile.mkdtemp(prefix="prepush-audit-")
    try:
        env = audit_env(base_env, home, terms)
        steps = [run_step("audit-privacy", [py, "-m", "halo_harness", "audit", "privacy"], logdir, env=env),
                 run_step("audit-commits", [py, "-m", "halo_harness", "audit", "privacy", "--commits"], logdir,
                          env=env)]
    finally:
        shutil.rmtree(home, ignore_errors=True)
    return steps
