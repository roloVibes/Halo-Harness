"""A stand-in for someone else's long-lived binary (an MCP server, a model server, a tool command): it records its
pid and the HALO_OWNER marker it was given, then sleeps until something ends it. It watches nothing.

    python closing_sleeper.py <out.json>
"""
import json
import os
import sys
import time

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump({"pid": os.getpid(), "marker": os.environ.get("HALO_OWNER", ""),
               "watch": os.environ.get("HALO_OWNER_WATCH", "")}, fh)
while True:
    time.sleep(1)
