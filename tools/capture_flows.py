"""tools/capture_flows.py -- render docs/media/studio-workflows-tab.png and docs/media/studio-workflows-try.png (Halo
3.6.0.0 R2): Studio's Agents -> 2 · Workflows over the crew rig (tests/helpers/crew_rig.py: a scratch home, a git repo,
the mock upstream, the builder's scripted model), driven by tests/helpers/studio_flows.py in headless Chrome at
1500 x 900 -- a copied starter's form with its steps drawn beside it (a repeat's loop mark), then a Try it run step by
step.

    python tools/capture_flows.py [--out DIR]     (default: docs/media)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAMES = ("studio-workflows-tab.png", "studio-workflows-try.png")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(REPO / "docs" / "media"))
    args = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    from tests.helpers.chrome_driver import driver_env
    tmp = Path(tempfile.mkdtemp(prefix="capture-flows-"))
    try:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_flows", str(tmp)], cwd=str(REPO), env=driver_env(REPO),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        missing = [n for n in NAMES if not (tmp / n).is_file()]
        if r.returncode != 0 or missing:
            print(f"capture_flows: the driver failed (exit {r.returncode}, missing {missing}):\n{(r.stdout + r.stderr)[-2000:]}", file=sys.stderr)
            return 1
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for n in NAMES:
            shutil.copyfile(tmp / n, out / n)
            print(f"capture_flows: {out / n} ({(out / n).stat().st_size} bytes)")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
