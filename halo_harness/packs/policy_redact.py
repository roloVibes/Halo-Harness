"""halo_harness.packs.policy_redact -- a policy's `redact: [env names]` (Halo 3.3.10.0; docs/EXTENSION_API.md
"Policy hooks"): the value of each named environment variable is taken out of what Halo sends a policy hook, the
tool input before the call and (3.3.10.0 R2) the tool's result after it, before the request leaves Halo.

    redact(value, names, env=None) -> value with each secret replaced by `[redacted:<NAME>]`
"""

from __future__ import annotations

import os


def redact(value, names, env=None):
    """`value` with every non-empty value of the environment variables `names` replaced by `[redacted:<NAME>]`."""
    env = os.environ if env is None else env
    secrets = [(n, env.get(n)) for n in names or () if isinstance(env.get(n), str) and env.get(n)]
    if not secrets:
        return value

    def walk(v):
        if isinstance(v, str):
            for name, secret in secrets:
                v = v.replace(secret, f"[redacted:{name}]")
            return v
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v
    return walk(value)
