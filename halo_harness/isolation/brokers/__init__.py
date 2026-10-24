"""halo_harness.isolation.brokers -- one file per secret broker (Halo 3.1.8.0 R5).

A broker is a module with `NAME`, `CLI` (the command it needs on PATH, or
""), `present(which) -> bool` and `read(ref, *, account, runner, which,
environ) -> str` that raises `BrokerError` with one line naming the ref
(never the value). `secrets.broker: <name>` picks one; `1password` lives
in `onepassword.py` (a module name cannot start with a digit). A second
broker is one more file here and one row in `MODULES`.
"""

from __future__ import annotations

import importlib

MODULES = {"1password": "onepassword", "env": "env"}


class BrokerError(RuntimeError):
    """One factual line: which ref could not be read, or which broker is missing."""


def load(name: str):
    module = MODULES.get(str(name or ""))
    if module is None:
        raise BrokerError(f"secrets: no broker named {name!r} (known: {', '.join(MODULES)})")
    return importlib.import_module(f"halo_harness.isolation.brokers.{module}")
