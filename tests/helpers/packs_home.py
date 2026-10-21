"""tests.helpers.packs_home -- a scratch home and repo for the packs tests
(Halo 3.2.0.0 R1).

    with PacksHome() as h:                 # tests.helpers.config_seed.ConfigHome + a clean packs cache
        src = h.source()                   # a fresh copy of tests/fixtures/packs/doc-review to install from
        h.install(src, enable=True, grants=["hooks"])
        code, out, err = h.cli("list", "--json")

`h.cli` runs `halo pack <argv> --cwd <repo>` in process and captures stdout and
stderr. Nothing here touches the real home: ConfigHome points
BRIDGE_TEST_HOME at a temp folder and restores every provider variable.
"""

from __future__ import annotations

import contextlib
import io
import shutil
from pathlib import Path

from tests.helpers.config_seed import ConfigHome

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "packs"
DOC_REVIEW = FIXTURES / "doc-review"


class PacksHome(ConfigHome):
    def __enter__(self):
        super().__enter__()
        from halo_harness.packs import registry
        registry.invalidate()
        self.sources = self.home / "sources"
        return self

    def __exit__(self, *exc):
        from halo_harness.packs import registry
        registry.invalidate()
        return super().__exit__(*exc)

    def source(self, name: str = "doc-review", *, folder: str = "") -> Path:
        """A copy of a fixture pack, as a source folder to install from."""
        dest = self.sources / (folder or name)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(FIXTURES / name, dest)
        return dest

    def install(self, src: Path, *, project: bool = False, enable: bool = False, grants=()) -> None:
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable as enable_pack
        from halo_harness.packs.install import install
        ok, lines = install(str(src), project=project, cwd=self.repo)
        assert ok, lines
        if enable:
            ok, lines = enable_pack(find("doc-review", cwd=self.repo), grant=list(grants))
            assert ok, lines

    def cli(self, *argv) -> "tuple[int, str, str]":
        from halo_harness.packs.cli import cmd_pack
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cmd_pack(list(argv) + ["--cwd", str(self.repo)])
        return code, out.getvalue(), err.getvalue()

    @property
    def packs(self) -> Path:
        return self.state / "packs"
