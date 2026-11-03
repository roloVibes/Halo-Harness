"""The setup-blocks pack's Setup check (docs/EXTENSION_API.md "Setup blocks"): Setup's checks job runs this in the
pack's folder when its row is ticked; exit 0 is green, and what it prints is the row's lines. Plain Python, nothing
of Halo imported. The tests' seams: HALO_SETUP_TEST_FAIL=1 prints the same two lines, then exits 1;
HALO_SETUP_TEST_ECHO_ENV=1 also prints every variable of its environment whose name says KEY or TOKEN, with its
value (the tests read the frames for a provider key Halo holds: it never reaches a pack's check).
"""

import os
import sys

failed = os.environ.get("HALO_SETUP_TEST_FAIL") == "1"
print("review service: asked")
print("review service: no answer" if failed else "review service: answered")
if os.environ.get("HALO_SETUP_TEST_ECHO_ENV") == "1":
    for name in sorted(os.environ):
        if "KEY" in name.upper() or "TOKEN" in name.upper():
            print(f"env {name}={os.environ[name]}")
sys.exit(1 if failed else 0)
