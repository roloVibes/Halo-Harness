"""tests.helpers.browser_standin -- a stand-in for a Halo session that holds Halo's browser (tests/test_browser_closing.py):
it starts one (browser_cdp.Browser, the profile named in argv[2], under the home in argv[1]), opens a page, prints
one JSON line {pid, browser, profile} and then waits to be ended. argv[3] == "close": it runs closing.close() instead
of waiting (the closing procedure every way out runs) and prints "closed"."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def main() -> None:
    from halo_harness import browser_cdp, closing
    b = browser_cdp.Browser(sys.argv[2], home=sys.argv[1]).start()
    b.open("data:text/html,<title>stand-in</title><p>held</p>")
    print(json.dumps({"pid": __import__("os").getpid(), "browser": b.proc.pid, "profile": b.profile,
                      "tmp": str(getattr(b, "tmp", "") or "")}), flush=True)
    if len(sys.argv) > 3 and sys.argv[3] == "close":
        closing.close(say=lambda _l: None)
        print("closed", flush=True)
        return
    time.sleep(600)


if __name__ == "__main__":
    main()
