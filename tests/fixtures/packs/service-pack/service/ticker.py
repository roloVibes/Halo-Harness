"""The service-pack fixture's one program. As a service (no arguments): rewrite the health file the supervisor named
(HALO_SERVICE_HEALTH) every 0.1 s, saying whether a provider key reached it; end with 0 when the stop file appears
(HALO_SERVICE_STOP); end with 3 once when the data folder holds crash.flag (it removes the flag first). As the pack's
command (`--say <words>`): print the words."""

import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    if sys.argv[1:2] == ["--say"]:
        print("the pack's own program says: " + " ".join(sys.argv[2:]))
        print("HALO_PACK_ID=" + os.environ.get("HALO_PACK_ID", ""))  # 3.3.14.0 R1: the id, not the folder's name
        return 0
    health, stop = Path(os.environ["HALO_SERVICE_HEALTH"]), Path(os.environ["HALO_SERVICE_STOP"])
    flag = health.parent / "crash.flag"
    if flag.exists():
        flag.unlink()
        health.write_text(json.dumps({"state": "crashing", "line": "crashed on purpose"}), encoding="utf-8")
        return 3
    keys = [k for k in os.environ if k.startswith(("OPENROUTER_", "ANTHROPIC_"))]
    while not stop.exists():
        health.write_text(json.dumps({"state": "ok", "line": f"ticking, provider keys here: {len(keys)}",
                                      "service": os.environ.get("HALO_SERVICE")}), encoding="utf-8")
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
