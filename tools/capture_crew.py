"""tools/capture_crew.py -- render docs/media/studio-agents-tab.png and docs/media/studio-builder-preview.png (Halo
3.6.0.0 R1): Studio's Agents -> 1 · Agents over the crew rig (tests/helpers/crew_rig.py: a scratch home, a git repo,
the mock upstream, the builder's scripted model), driven by tests/helpers/studio_crew.py in headless Chrome at
1500 x 900 -- the builder's preview of "make a security gate" (its widening lines unticked), then the tab with a
copied starter's form and its Try it result.

    python tools/capture_crew.py [--out DIR]     (default: docs/media)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAMES = ("studio-agents-tab.png", "studio-builder-preview.png")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(REPO / "docs" / "media"))
    args = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    from tests.helpers.chrome_driver import driver_env
    tmp = Path(tempfile.mkdtemp(prefix="capture-crew-"))
    try:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_crew", str(tmp)], cwd=str(REPO), env=driver_env(REPO),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        missing = [n for n in NAMES if not (tmp / n).is_file()]
        if r.returncode != 0 or missing:
            print(f"capture_crew: the driver failed (exit {r.returncode}, missing {missing}):\n{(r.stdout + r.stderr)[-2000:]}", file=sys.stderr)
            return 1
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for n in NAMES:
            shutil.copyfile(tmp / n, out / n)
            print(f"capture_crew: {out / n} ({(out / n).stat().st_size} bytes)")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
