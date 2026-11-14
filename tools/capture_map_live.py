"""tools/capture_map_live.py -- render docs/media/studio-map-lit.png, studio-map-helper.png, studio-map-feed.png and
studio-map-replay.png (Halo 3.6.0.0 R4): Studio's Agents -> 3 · Map lit while a session runs, over the session rig
(tests/helpers/studio_session_rig.py + studio_live_rig.py: a scratch home, a fake session's frames), driven by
tests/helpers/studio_map_live.py in headless Chrome at 1500 x 900 -- a hand-off moving on a line, a made-up helper with
Save as an agent, the drawer with an ask, and a past run replayed on the map.

    python tools/capture_map_live.py [--out DIR]     (default: docs/media)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAMES = ("studio-map-lit.png", "studio-map-helper.png", "studio-map-feed.png", "studio-map-replay.png")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(REPO / "docs" / "media"))
    args = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    from tests.helpers.chrome_driver import driver_env
    tmp = Path(tempfile.mkdtemp(prefix="capture-map-live-"))
    try:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_map_live", str(tmp)], cwd=str(REPO), env=driver_env(REPO),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        missing = [n for n in NAMES if not (tmp / n).is_file()]
        if r.returncode != 0 or missing:
            print(f"capture_map_live: the driver failed (exit {r.returncode}, missing {missing}):\n{(r.stdout + r.stderr)[-2000:]}", file=sys.stderr)
            return 1
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for n in NAMES:
            shutil.copyfile(tmp / n, out / n)
            print(f"capture_map_live: {out / n} ({(out / n).stat().st_size} bytes)")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
