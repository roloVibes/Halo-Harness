"""The first-run pack's Setup check (`contributes.setup`, block `run`): Setup's Check page runs it as one more row,
`pack:first-run:run`. It runs `halo start --yes --no-studio` -- the guided first run straight through, the plan
approved -- and its exit is the row's: 0 green, anything else red with the last lines. Halo hands a pack's check the
environment a pack hook gets (no provider key from Halo's own environment); the run reads the keys from Halo's env
file, as every halo run does.
"""

import subprocess
import sys


def main() -> int:
    proc = subprocess.run([sys.executable, "-m", "halo_harness", "start", "--yes", "--no-studio"],
                          stdin=subprocess.DEVNULL)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
