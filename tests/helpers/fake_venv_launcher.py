"""Stands in for an installed Halo's python on Windows (the venv's python.exe is a launcher): it runs the rest of its
argv as a child and exits with that child's code, so the pid a Popen gets is not the pid the program reports."""
import subprocess
import sys

sys.exit(subprocess.call(sys.argv[1:]))
