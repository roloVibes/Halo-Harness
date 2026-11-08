"""__NAME__'s Setup check (pack.yaml contributes.setup, kind check): Setup's checks job runs it in the pack's folder
when the owner ticks its row; exit 0 is green and what it prints is the row's lines. Plain Python, nothing of Halo
imported. Make it check what your pack needs from this machine.
"""

import platform
import sys

print(f"python {platform.python_version()}: found")
sys.exit(0 if sys.version_info >= (3, 10) else 1)
