"""The design pack's Studio rig: a live Studio in this test's scratch home with the pack linked and granted
(`halo_harness.ext.testing.studio`), the turn runner faked on the routes' own module (no model call), and the calls
the tests make by the paths they used before the pack (`/api/design/...`, `/design-files/...`), sent where the pack
answers them now (`/api/packs/design/design/...`, its `_files/` route with the token in `?t=`).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from tests.run import PACK

HERO = '<!doctype html><html><head><style>:root{--space:16px}body{padding:var(--space)}</style></head><body><h1>Hello</h1></body></html>'
KNOBS = [{"name": "Spacing", "kind": "range", "target": "css:--space", "min": 0, "max": 64, "step": 1, "value": 16},
         {"name": "Title size", "kind": "range", "target": "craft:designcraft:size", "min": 8, "max": 96, "value": 32}]
OLD_API, OLD_FILES = "/api/design/", "/design-files/"


def _fake_runner(gate=None):
    def runner(cmd, cwd, env, on_line):
        d = Path(cwd) / "artboards" / "hero"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(HERO, encoding="utf-8")
        (d / "controls.json").write_text(json.dumps(KNOBS), encoding="utf-8")
        on_line(json.dumps({"type": "system", "subtype": "init"}))
        if gate is not None:
            gate.wait(10)
        on_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Making the hero."}]}}))
        on_line(json.dumps({"type": "result", "result": "Done: hero.", "total_cost_usd": 0.02}))
        return 0
    return runner


class _Studio:
    def __enter__(self):
        from halo_harness.ext import data_dir, host, testing
        self.studio = testing.studio(PACK).__enter__()
        self.api = self.studio.module("server/api.py")
        self.api.RUNNER, self.api.REGISTERED = _fake_runner(), set()
        self.state = Path(host.state_dir())
        self.root = Path(data_dir("design")) / "projects"  # the projects folder (~/.halo/design before the pack)
        self.base, self.token, self.srv = self.studio.base, self.studio.token, self.studio.srv
        return self

    def __exit__(self, *a):
        self.api.RUNNER = self.api.REGISTERED = None
        self.studio.__exit__(*a)

    def path(self, p: str) -> str:
        return self.studio.route(p[len(OLD_API):]) if p.startswith(OLD_API) else (
            self.studio.route("_files/" + p[len(OLD_FILES):]) if p.startswith(OLD_FILES) else p)

    def call(self, method, path, body=None, token=None):
        return self.studio.call(method, self.path(path), body, token=token)

    def raw(self, path, token: bool = True):
        return self.studio.raw(self.path(path), token=token)

    def run_turn(self, slug, prompt="A hero"):
        status, r = self.call("POST", f"/api/design/{slug}/run", {"prompt": prompt})
        assert status == 200, (status, r)
        seen, since, deadline = [], 0, time.time() + 15
        while time.time() < deadline:
            _, p = self.call("GET", f"/api/design/{slug}/turn/{r['turn']}?since={since}")
            seen += p["events"]
            since = p["next"]
            if p["done"]:
                return seen, p
            time.sleep(0.05)
        raise AssertionError("the turn never finished")

    def seeded(self, name="Hero Lab"):
        slug = self.call("POST", "/api/design/projects", {"name": name, "model": "or:v/eyes"})[1]["slug"]
        self.run_turn(slug)
        return slug
