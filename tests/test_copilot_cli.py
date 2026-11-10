"""tests.test_copilot_cli -- `halo copilot` in a scratch home against the mock (Halo 3.3.17.0 R1, copilot_cli.py):
`halo copilot` alone is status; not set up and not signed in each say their one line; signin (the browser stub),
status (who, the tenant, the api, until when, the scopes to consent to), ask (the answer, then the citations
numbered; --json, --file, --no-web, --api graph-beta), signout; a failure is one line on stderr and exit 1; the
command is wired in cli.py and in the completion list.

Run: python -m tests.test_copilot_cli
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.mock_copilot import USER  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def run(argv) -> "tuple[int, str, str]":
    from halo_harness.cli import _main
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = _main(["copilot", *argv])
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


@test
def test_not_set_up_then_not_signed_in(ctx: Ctx):
    with CopilotRig(configured=False):
        code, out, _ = run([])
        ctx.check(f"`halo copilot` alone is status: not set up, got {out!r}", code == 0 and "Copilot: not set up" in out
                  and "copilot.tenant" in out)
    with CopilotRig():
        code, out, _ = run(["status"])
        ctx.check(f"configured: not signed in, the tenant and the scopes, got {out!r}", code == 0
                  and "not signed in -- run `halo copilot signin`" in out and "tenant: pretend-tenant" in out
                  and "scopes an admin consents to: https://workiq.svc.cloud.microsoft/.default" in out)
        code, out, err = run(["ask", "hello"])
        ctx.check(f"ask before signin: one line on stderr, exit 1, got {code} {err!r}", code == 1
                  and err.strip() == "Copilot: not signed in -- run `halo copilot signin`." and not out)


@test
def test_signin_status_ask_signout(ctx: Ctx):
    with CopilotRig() as r:
        code, out, _ = run(["signin"])
        ctx.check(f"signed in, got {out!r}", code == 0 and f"signed in as {USER}" in out and r.opened)
        code, out, _ = run(["status"])
        ctx.check(f"status: who and until when, got {out!r}", code == 0 and f"Copilot: signed in as {USER}" in out
                  and "valid until" in out and "api: workiq" in out)
        code, out, _ = run(["status", "--json"])
        data = json.loads(out)
        ctx.check(f"status --json, got {data}", data["signed_in"] and data["username"] == USER and data["api"] == "workiq")
        code, out, _ = run(["ask", "what changed this week"])
        ctx.check(f"the answer then the citations numbered, got {out!r}", code == 0 and out.startswith("Work IQ heard: what changed")
                  and "[1] Q3 plan.docx -- https://pretend.sharepoint.com/q3.docx" in out and "[2] Standup notes" in out)
        code, out, _ = run(["ask", "the budget", "--file", "https://pretend.sharepoint.com/b.xlsx", "--no-web",
                            "--api", "graph-beta", "--json"])
        a = json.loads(out)
        ctx.check(f"--json --file --no-web --api graph-beta, got {a}", a["api"] == "graph-beta" and "b.xlsx" in a["text"]
                  and "web off" in a["text"] and a["citations"][0]["title"] == "Budget.xlsx")
        code, out, _ = run(["signout"])
        ctx.check(f"signout says what went, got {out!r}", code == 0 and "HALO_SECRET_COPILOT_REFRESH" in out)
        code, out, _ = run([])
        ctx.check("then not signed in", "not signed in" in out)


@test
def test_wiring(ctx: Ctx):
    from halo_harness.completion_cli import SUBCOMMANDS
    ctx.check("copilot is in the completion list", "copilot" in SUBCOMMANDS)
    code, out, err = run(["nope"])
    ctx.check(f"an unknown verb: one line, exit 2, got {code} {err!r}", code == 2 and "no verb 'nope'" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
