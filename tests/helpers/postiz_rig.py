"""tests.helpers.postiz_rig -- shared pieces of the Postiz flow tests (R4):
the fake CLI directory, a flow spec with `live`/`every` set, a whole run over
FakeComfy and a scripted marketing org, the CLI entry point and the secret scan.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path

from tests.helpers import fake_postiz
from tests.helpers.fake_comfy import FakeComfy
from tests.helpers.fake_flow import FakeOrg, make_adapters, new_run, template_spec

KEY = "pzk-SECRET-0123456789"
FOUR = "youtube,instagram,x,tiktok"
COPY4 = ('```json\n{"youtube": {"title": "Halo 3.0.4 teaser", "text": "Watch the flow run"}, "instagram": {"text": "ig caption #halo"}, '
         '"x": {"text": "short x post #halo"}, "tiktok": {"text": "tt caption #halo"}}\n```')


def spec_with(live: bool, every: str = "10s"):
    spec = template_spec()
    for s in spec["steps"]:
        if s["id"] == "publish":
            s["live"] = live
        if s["id"] == "measure":
            s["every"] = every
    return spec


def _fake(**options):
    d = Path(tempfile.mkdtemp(prefix="fake-postiz-"))
    log = d / "calls.jsonl"
    fake_postiz.install(d, log, **options)
    return d, log


def _go(spec, platforms=FOUR, copy=COPY4, project="postiz-run"):
    from halo_harness.flows.run import run
    with FakeComfy() as fake:
        run_dir = new_run(spec, project=project, platforms=platforms)
        report = run(run_dir, adapters=make_adapters(fake.url, run_org=FakeOrg(copy=copy), auto_accept=True))
    return run_dir, report


def _project(run_dir):
    from halo_harness.flows.state import read_flow
    from halo_harness.design.store import Project
    return Project(Path(read_flow(run_dir)["project_path"]))


def _cli(*argv):
    from halo_harness.cli import main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue(), err.getvalue()


def no_secret(ctx, run_dir, extra=""):
    proj = _project(run_dir)
    blob = "".join(p.read_text(encoding="utf-8") for p in (proj.path / "posts.json", proj.path / "metrics.jsonl",
                                                          run_dir / "events.jsonl", run_dir / "report.json")) + extra
    ctx.check("no secret value in posts.json, metrics.jsonl, events.jsonl, report.json or the output", KEY not in blob)


