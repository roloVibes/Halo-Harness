"""The signal pack's one program (halo_signal/main.py says its verbs): the bridge service, `/signal ...`, Setup's
checks. Run with Halo's own Python (`${halo_python}`), so `halo_harness.ext` imports."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_signal.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
