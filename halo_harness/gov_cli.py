"""halo_harness.gov_cli -- Halo 2.0.5 round 4: `halo gov [host]`.

Prints every gateway bucket the Governor knows (`inspect_all()`: rate
vs ceiling, in-flight, waiting, cooldown, last event) and, given a host
argument, that host's recent calls (the per-bucket jsonl tail -- agent,
role, session, model, status per call). `--json` emits the same data as
one JSON object for scripting. Read-only, never touches a network.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlparse


def _bucket_key_for_arg(host_arg: str) -> str:
    """Accept a bare host, a `host:` bucket key, or a full base URL. The
    hostname is taken portless (urlparse's .hostname), matching the
    choke point's own bucket keys."""
    if host_arg.startswith("host:") or host_arg.startswith("provider:"):
        return host_arg
    parsed = urlparse(host_arg if "//" in host_arg else "//" + host_arg)
    return "host:" + (parsed.hostname or host_arg).lower()


def _format_bucket(st: dict) -> str:
    cd = st.get("cooldown_remaining") or 0.0
    cd_txt = f", cooldown {cd:.0f}s" if cd > 0 else ""
    last = st.get("last_event") or {}
    ev = f", last: {last.get('event')}" if last.get("event") else ""
    return (f"  {st.get('key')}: {st.get('rate')}/{st.get('rate_ceiling')} rps, "
            f"in-flight {st.get('inflight')}/{st.get('max_inflight')}, "
            f"waiting {st.get('waiting')}{cd_txt}{ev}")


def cmd_gov(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo gov", add_help=True,
                                     description="Show the Governor's gateway buckets (read-only)")
    parser.add_argument("host", nargs="?", help="one gateway host (or base URL): also show its recent calls")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    from halo_harness.providers import governor
    buckets = governor.inspect_all()
    recent = []
    key = None
    if args.host:
        key = _bucket_key_for_arg(args.host)
        recent = governor.recent_calls(key, limit=30)

    if args.json:
        print(json.dumps({"buckets": buckets, "recent_calls": recent}, indent=2, default=str))
        return 0

    if not buckets:
        print("No governed gateways yet (buckets appear once a governed request runs).")
    else:
        print("Governor gateway buckets:")
        for st in buckets:
            print(_format_bucket(st))
        degraded = governor.governor_state.is_degraded() if hasattr(governor, "governor_state") else None
        from halo_harness.providers.governor_state import is_degraded
        d = is_degraded()
        if d:
            print(f"  ! state not persisting: {d}")
    if args.host:
        print(f"\nRecent calls for {key}:")
        if not recent:
            print("  (none logged yet)")
        for rec in recent:
            ok = rec.get("ok")
            verdict = {True: "ok", False: "overload", None: "neutral"}[ok] if ok is not None else "neutral"
            print(f"  {rec.get('agent', '?'):>10} {str(rec.get('role', '?')):>12} "
                  f"{str(rec.get('status', '-')):>3} {verdict:>8}  {str(rec.get('model') or '')}")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_gov(sys.argv[1:]))
