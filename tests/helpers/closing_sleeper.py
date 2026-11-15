"""A stand-in for someone else's long-lived binary (an MCP server, a model server, a tool command): it records its
pid and the HALO_OWNER marker it was given, then sleeps until something ends it. It watches nothing.

    python closing_sleeper.py <out.json> [<grandchild out.json>]

With a second path it first starts a grandchild sleeper with the plain standard library (no Halo code: a child's
child whose own command line never names any marker) and records its pid too.
"""
import json
import os
import subprocess
import sys
import time

info = {"pid": os.getpid(), "marker": os.environ.get("HALO_OWNER", ""), "watch": os.environ.get("HALO_OWNER_WATCH", "")}
if len(sys.argv) > 2:
    grand = subprocess.Popen([sys.executable, os.path.abspath(__file__), sys.argv[2]], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    info["grandchild"] = grand.pid
with open(sys.argv[1] + ".tmp", "w", encoding="utf-8") as fh:
    json.dump(info, fh)
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
while True:
    time.sleep(1)
