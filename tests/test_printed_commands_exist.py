"""tests.test_printed_commands_exist -- fx studio batch 2: a command Halo prints or offers runs. Studio's Themes page
and two docs promise `halo config unset theme`; `halo config unset <key>` now exists. The hints that named
`halo config show`, `halo sessions`, `halo setup roles` (for a missing main model), `--step machines`,
`halo agents schedule list` and `halo workflows test` name commands that exist.
Run: python -m tests.test_printed_commands_exist
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ROOT = Path(__file__).resolve().parent.parent


def _run(argv: list) -> "tuple[int, str, str]":
    from halo_harness.config_cli import cmd_config
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_config(argv)
    return rc, out.getvalue(), err.getvalue()


@test
def test_config_unset_puts_a_key_back_to_its_default(ctx: Ctx):
    from halo_harness import theme as T
    rc, _, err = _run(["set", "theme", "claude-light"])
    ctx.check(f"a theme set, got {rc} {err!r}", rc == 0 and T.get_config_value("theme", default=None) == "claude-light")
    rc, out, err = _run(["unset", "theme"])
    ctx.check(f"`halo config unset theme`: 0, the default again, got {rc} {out!r} {err!r}",
              rc == 0 and T.get_config_value("theme", default=None) is None and "theme" in out)
    rc, out, err = _run(["get", "theme"])
    ctx.check(f"get says unset, got {out!r}", rc == 0 and "unset" in out)
    rc, out, err = _run(["unset", "theme"])
    ctx.check(f"unset again: 1, one line, got {rc} {err!r}", rc == 1 and "'theme' is not set" in err)
    # written straight to config.json: `halo config set` refuses a key nothing reads (sessions-storage), and this
    # check is about unset taking a dotted leaf and the sections it leaves empty
    T.set_config_value("fxtest.extra.port", 5)
    rc, _, _ = _run(["unset", "fxtest.extra.port"])
    cfg = json.loads((Path(T._config_path())).read_text(encoding="utf-8"))
    ctx.check(f"a dotted key: the leaf and its empty sections go, got {rc} {cfg}", rc == 0 and "fxtest" not in cfg)
    rc, out, _ = _run(["--help"])
    ctx.check(f"the usage names unset, got {out!r}", "unset <key>" in out)


BAD = {
    r"halo config show": "the verb is `get`",
    r"`halo sessions`": "there is no `halo sessions`",
    r"`halo setup roles` or the wizard's roles step": "the roles step is gone; a main model is Setup's Model page",
    r"linux, check, machines": "`--step machines` is not a page",
    r"halo agents schedule": "there is no `halo agents schedule`",
    r"halo workflows test": "there is no `halo workflows test`",
}


@test
def test_no_hint_names_a_command_that_does_not_exist(ctx: Ctx):
    files = [p for d in ("halo_harness", "docs") for p in (ROOT / d).rglob("*")
             if p.suffix in (".py", ".ts", ".tsx", ".md") and "dist" not in p.parts and "node_modules" not in p.parts
             and p.name != "changelog.md"]
    hits = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        for pat, why in BAD.items():
            for m in re.finditer(pat, text):
                hits.append(f"{p.relative_to(ROOT)}:{text.count(chr(10), 0, m.start()) + 1}: {why}")
    ctx.check(f"{len(files)} files read, none names a missing command, got {hits}", len(files) > 100 and hits == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
