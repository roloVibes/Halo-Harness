"""tests.helpers.coach_names -- importing it puts the coach pack's modules under their old names (Halo 3.4.0.0 B2), so a
moved coach test needs one line: `import tests.helpers.coach_names  # noqa: F401`. See tests/helpers/coach_pack.py."""
from tests.helpers import coach_pack

coach_pack.install_names()
