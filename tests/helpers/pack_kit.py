"""tests.helpers.pack_kit -- a scratch home for the pack kit's tests (Halo 3.3.12.0 R4): `halo pack new` into it,
a model catalog a scaffold's bios resolve against, a PATH with (or without) a fake `rg`.

    with KitHome() as k:                       # tests.helpers.packs_home.PacksHome: a fresh BRIDGE_TEST_HOME
        folder = k.new("demo", "agents", "teams")          # halo pack new demo --kinds agents,teams --dir <work>
        code, out, err = k.cli("inspect", str(folder))
        with k.path(fake_rg=True): ...         # PATH = a scratch bin (+ a fake rg) + Python's folder

Nothing here reaches a model or the network; the fake `rg` prints a version and exits 0.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

from tests.helpers.packs_home import PacksHome

LOCAL_TOOLS = [{"ref": "ol:qwen3:8b", "provider": "ollama", "tools": True, "context_tokens": 32768}]


class KitHome(PacksHome):
    def __enter__(self):
        super().__enter__()
        self.work = self.home / "work"
        self.work.mkdir()
        self.catalog(LOCAL_TOOLS)
        return self

    def new(self, pack_id: str, *kinds, all_kinds: bool = False, github: bool = True, **kw) -> Path:
        from halo_harness.packs.scaffold import new
        ok, lines = new(pack_id, kinds=list(kinds), all_kinds=all_kinds, folder=self.work, github=github, **kw)
        assert ok, lines
        return self.work / pack_id

    def manager_needs(self, pack_id: str) -> list:
        """The Pack Manager's row's `needs` for one pack (GET pack/manager's payload, read in process)."""
        from halo_harness.packs.manager import payload
        return next(r for r in payload(cwd=self.repo)["packs"] if r["id"] == pack_id)["needs"]

    @contextmanager
    def path(self, *, fake_rg: bool = False):
        """PATH = a scratch bin (with a fake rg when asked) + Python's folder; restored after."""
        bin_dir = self.home / ("bin-rg" if fake_rg else "bin")
        bin_dir.mkdir(exist_ok=True)
        if fake_rg and os.name == "nt":
            (bin_dir / "rg.bat").write_text("@echo ripgrep 14.1.0\r\n", encoding="utf-8")
        elif fake_rg:
            (bin_dir / "rg").write_text("#!/bin/sh\necho ripgrep 14.1.0\n", encoding="utf-8")
            (bin_dir / "rg").chmod(0o755)
        saved = os.environ.get("PATH")
        os.environ["PATH"] = os.pathsep.join([str(bin_dir), str(Path(sys.executable).parent)])
        try:
            yield bin_dir
        finally:
            os.environ["PATH"] = saved or ""
