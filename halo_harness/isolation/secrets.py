"""halo_harness.isolation.secrets -- `secrets: broker` (Halo 3.1.8.0 R5).

At spawn, each of a bio's `environment.secrets` refs is read through the
broker (`isolation/brokers/<name>.py`) and its value goes into the worker's
environment ONLY: never a file, never a transcript, never a frame. The
worker's environment also names the keys (`HALO_SECRET_KEYS`, names only),
so its own `tool_child_env` strips them from every tool child (Bash, MCP,
hooks) unless the bio's `environment.pass_to_tools` names them
(`HALO_SECRET_PASS`); the harness's own provider keys never reach a tool
child either way. What the runner keeps of the worker (its reply and error
tails) has every value replaced by `<redacted>`. A ref that cannot be read
is one line naming the ref, and the lane stops with it.

`halo secrets check [--lineup L | --bio B]`: the broker on PATH, each ref
readable -- printed as names and "ok" only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from typing import Optional

from halo_harness.isolation import Stop
from halo_harness.isolation.brokers import BrokerError, load

KEYS_ENV, PASS_ENV = "HALO_SECRET_KEYS", "HALO_SECRET_PASS"


class SecretStop(Stop):
    """The one line a lane stops with."""


def resolve(secrets: dict, *, runner=subprocess.run, which=shutil.which, environ=None) -> dict:
    """`{env name: value}` for every ref; raises SecretStop naming the first ref that cannot be read."""
    if not secrets.get("broker"):
        raise SecretStop(f"secrets: {len(secrets.get('refs') or [])} ref(s) in environment.secrets, no secrets.broker set")
    try:
        broker = load(secrets["broker"])
        values = {}
        for env_name, ref in secrets.get("refs") or []:
            values[env_name] = broker.read(ref, account=secrets.get("account") or "", runner=runner, which=which,
                                           environ=environ)
        return values
    except BrokerError as e:
        raise SecretStop(str(e)) from None


def worker_env(values: dict, passes) -> dict:
    """The names the worker's environment carries beside the values (never a value)."""
    out = {KEYS_ENV: ",".join(sorted(values))}
    keep = [k for k in passes or () if k in values]
    if keep:
        out[PASS_ENV] = ",".join(sorted(keep))
    return out


def strip_keys(env: dict) -> set:
    """The broker keys a tool child of this process never sees (tool_child_env's one call)."""
    named = {k.strip() for k in str(env.get(KEYS_ENV) or "").split(",") if k.strip()}
    passed = {k.strip() for k in str(env.get(PASS_ENV) or "").split(",") if k.strip()}
    return named - passed


def scrub(text: str, values) -> str:
    """`text` with every value replaced by `<redacted>`."""
    out = str(text or "")
    for value in sorted({v for v in values if v and len(v) >= 4}, key=len, reverse=True):
        out = out.replace(value, "<redacted>")
    return out


def line(secrets: Optional[dict]) -> str:
    """'secrets: 1password (3 refs)'."""
    if not secrets:
        return ""
    n = len(secrets.get("refs") or [])
    return f"secrets: {secrets.get('broker') or '(no broker)'} ({n} ref{'' if n == 1 else 's'})"


def check_lines(name: str, secrets: Optional[dict], *, runner=subprocess.run, which=shutil.which) -> "list[str]":
    """One line for the broker and one per ref: names and ok, never a value."""
    if not secrets:
        return [f"{name}: no secrets declared"]
    broker = secrets.get("broker") or ""
    try:
        mod = load(broker)
    except BrokerError as e:
        return [f"{name}: {e}"]
    found = mod.present(which)
    lines = [f"{name}: broker {broker}" + (f" ({mod.CLI} on PATH)" if found and mod.CLI else "" if found else
                                           f": no `{mod.CLI}` on PATH")]
    for env_name, ref in secrets.get("refs") or []:
        try:
            mod.read(ref, account=secrets.get("account") or "", runner=runner, which=which)
            lines.append(f"  {env_name}: ok")
        except BrokerError as e:
            lines.append(f"  {env_name}: {str(e).removeprefix('secrets: ')}")
    return lines


def _targets(args, cwd) -> "list[tuple[str, dict]]":
    from halo_harness import agents_yaml as A, teams_yaml as T
    from halo_harness.isolation import spec
    if args.bio:
        return [(f"bio {args.bio}", spec.resolve(None, "", A.resolve_agent_bio(args.bio, cwd=cwd), args.bio).secrets)]
    if args.lineup:
        tpl = T.resolve_team_template(args.lineup, cwd=cwd) or {}
        rows = [(f"lineup {args.lineup}", spec.resolve(tpl, args.lineup, None, "").secrets)]
        for e in tpl.get("agents") or []:
            if isinstance(e, dict) and e.get("agent"):
                got = spec.resolve(tpl, args.lineup, A.resolve_agent_bio(e["agent"], cwd=cwd), e["agent"]).secrets
                if got and got.get("refs"):
                    rows.append((f"lineup {args.lineup} / bio {e['agent']}", got))
        return rows
    from halo_harness.isolation.declared import declared
    return [(label, s) for label, _iso, s in declared(cwd=cwd) if s]


def cmd_secrets(argv: list, *, runner=subprocess.run, which=shutil.which) -> int:
    p = argparse.ArgumentParser(prog="halo secrets", description="Check the secret broker and each ref (names only).")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="the broker on PATH and each ref readable: names and ok, never a value")
    c.add_argument("--lineup", default=None, help="check one lineup and the bios it assigns")
    c.add_argument("--bio", default=None, help="check one bio")
    args = p.parse_args(argv)
    if args.cmd != "check":
        p.print_help()
        return 2
    from pathlib import Path
    rows = _targets(args, Path.cwd())
    if not rows:
        print("halo secrets: no lineup or bio here declares secrets")
        return 0
    bad = False
    for label, secrets in rows:
        lines = check_lines(label, secrets, runner=runner, which=which)
        bad = bad or any(not ln.endswith(": ok") and ln.startswith("  ") for ln in lines) or "no `" in lines[0]
        print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cmd_secrets(sys.argv[1:]))
