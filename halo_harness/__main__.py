"""`python -m halo_harness ...` entry point -- delegates straight to cli.main()."""

import sys

if __name__ == "__main__":  # 3.6.0.0 fx: a `halo --tmux` session takes its shell's environment before anything reads it
    from halo_harness.bg_run import take_tmux_env
    take_tmux_env()

from halo_harness.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
