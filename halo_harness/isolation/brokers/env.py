"""halo_harness.isolation.brokers.env -- `ENV:<KEY>`: a value from this process's environment.

For tests and for people without a broker. It is not a secret store: the
value is whatever the environment Halo started in holds; what the opt-in
adds is the rest of the round (the key reaches the worker only, joins the
run's strip list for its tool children, never lands in a file).
"""

from __future__ import annotations

import os
import shutil
import subprocess

from halo_harness.isolation.brokers import BrokerError

NAME, CLI = "env", ""


def present(which=shutil.which) -> bool:
    return True


def read(ref: str, *, account: str = "", runner=subprocess.run, which=shutil.which, environ=None) -> str:
    ref = str(ref)
    if not ref.startswith("ENV:") or not ref[4:].strip():
        raise BrokerError(f"secrets: {ref} is not an ENV:<KEY> reference")
    value = (os.environ if environ is None else environ).get(ref[4:].strip())
    if not value:
        raise BrokerError(f"secrets: {ref} is not set in this environment")
    return value
