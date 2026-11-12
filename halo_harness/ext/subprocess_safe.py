"""halo_harness.ext.subprocess_safe -- a pack's `subprocess` (Halo 3.4.1.2, PACKS-4): the same module as
halo_harness/subprocess_safe.py, offered through the extension API so a pack's code imports only `halo_harness.ext`.

    from halo_harness.ext import subprocess_safe as subprocess

`run` / `Popen` / `call` / `check_call` / `check_output` resolve a bare program name over the PATH folders, never the
current folder; everything else is the standard module's.
"""

import sys

from halo_harness import subprocess_safe as _safe

sys.modules[__name__] = _safe
