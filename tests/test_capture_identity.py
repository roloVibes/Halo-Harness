"""tests.test_capture_identity -- Halo 3.1.7.0 R2 "captures carry no real names":
every Studio capture tool draws the placeholder harness `you@studio` and no
absolute path of the machine it runs on (tools/capture_identity.py).

* the tools' source (parsed, never the pixels): each one imports the helper,
  calls `placeholder` before it serves Studio or enters a rig, `begin` before
  its scratch home, guards every page before it counts or shoots it, and
  never reads the machine's user or host itself;
* the helper: `placeholder` writes `fleet.name: you@studio` and every name
  Studio would draw reads `you` / `studio`; a `fleet_name` that answers this
  machine's `user@host` (a fake) stops it with the one line and exit 2;
  `restore` puts the real readers and the temp root back;
* the DOM guard: a home path, an AppData path or the machine's user or host
  name stops a tool (exit 1, the name masked); the fixtures' own names
  (`kali@lab`, a CI runner's "no runner") never do;
* every committed Studio picture is something a tool writes.
Run: python tests/test_capture_identity.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers import capture_source as S  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

import capture_identity as CI  # noqa: E402

test, TESTS = new_registry()


@test
def test_every_capture_tool_sets_the_placeholder_before_it_serves(ctx: Ctx):
    found = sorted(p.stem for p in (REPO / "tools").glob("capture_*.py")
                   if any(f"{s}(" in p.read_text(encoding="utf-8") for s in S.SERVES) and p.stem != "capture_identity")
    ctx.check(f"every tool that serves Studio is on the list, got {found}", set(found) <= set(S.TOOLS))
    for mod in S.TOOLS:
        ctx.check(f"{mod} imports tools/capture_identity.py", "from capture_identity import" in (REPO / "tools" / f"{mod}.py").read_text(encoding="utf-8"))
        for fn in S.functions(mod):
            for first, later in (("placeholder", S.SERVES), ("begin", {"scope_home"})):
                bad = S.missing_first(fn, first, later)
                ctx.check(f"{mod}.{fn.name} calls {first}() on every path before {sorted(later)}, not before: {bad}", not bad)


@test
def test_every_page_is_guarded_before_it_is_counted_or_shot(ctx: Ctx):
    seen = 0
    for mod in S.TOOLS:
        for fn in S.functions(mod):
            bad, n = S.unguarded(fn)
            seen += n
            ctx.check(f"{mod}.{fn.name}: every count and picture runs after a guard on its own path, unguarded: {bad}", not bad)
    ctx.check(f"the tools count and shoot pages, got {seen} calls", seen >= 20)


@test
def test_the_tools_never_read_the_machine_identity_themselves(ctx: Ctx):
    readers = ("gethostname", "getpass", "USERNAME", 'environ["USER', "environ.get(\"USER", "_user()", "_host()", "Path.home()")
    for mod in (*S.TOOLS, "capture_session_scenes"):
        text = (REPO / "tools" / f"{mod}.py").read_text(encoding="utf-8")
        hits = [r for r in readers if r in text]
        ctx.check(f"{mod} reads no user or host name of its own, got {hits}", not hits)


@contextlib.contextmanager
def _home():
    """A fresh scratch home for one test; the environment, the caches and the helper restored after."""
    from halo_harness.fleet import identity
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="cap-identity-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    try:
        yield state
    finally:
        CI.restore()
        identity.forget_cache()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(home, ignore_errors=True)


@test
def test_placeholder_draws_you_at_studio_and_restore_puts_the_readers_back(ctx: Ctx):
    from halo_harness.fleet import identity
    from halo_harness.remote import fleet_identity as FI
    tempfile.gettempdir()  # the module caches its root on first use: the baseline is that cached value
    real_user, real_host, sys_temp = FI._user, FI._host, tempfile.tempdir
    with _home() as state:
        other = state.parent / "rig-state"
        CI.placeholder(other)
        me = identity.harness()
        ctx.check(f"the process's harness is you@studio, got {me.get('name')}", identity.fleet_name() == "you@studio" and me.get("name") == "you@studio")
        ctx.check(f"its user and host read you / studio, got {me.get('user')} / {me.get('host')}", (me.get("user"), me.get("host")) == ("you", "studio"))
        ctx.check("a rig's own home is you@studio too", identity.fleet_name(other) == "you@studio" and identity.harness(other)["host"] == "studio")
        doc = json.loads((other / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"fleet.name is written into that home's config, got {doc}", doc.get("fleet", {}).get("name") == "you@studio")
        ctx.check("the scoped home's config names it too", json.loads((state / "config.json").read_text(encoding="utf-8"))["fleet"]["name"] == "you@studio")
        ctx.check(f"the temp root carries no home path, got {CI.leaks(tempfile.gettempdir())}", CI.leaks(tempfile.gettempdir()) == [])
        own = CI._saved.get("own")
    ctx.check("restore() puts the real user and host readers back", FI._user is real_user and FI._host is real_host)
    ctx.check("restore() puts the system temp root back and removes the capture's folder",
              tempfile.tempdir == sys_temp and (own is None or not Path(own).exists()))


@test
def test_placeholder_stops_when_studio_would_draw_this_machine(ctx: Ctx):
    from halo_harness.fleet import identity
    users, host = CI.real_names()
    fakes = [f"{users[0]}@{host}"]
    if users[0].lower() not in CI._placeholders():  # on a Kali box the user `kali` is the fixtures' own name
        fakes.append(f"{users[0]}@studio")
    for fake in fakes:
        with _home():
            saved = identity.fleet_name
            identity.fleet_name = lambda home_dir=None, _n=fake: _n  # a fake: this machine's own name
            out, code = io.StringIO(), None
            try:
                with contextlib.redirect_stdout(out):
                    CI.placeholder()
            except SystemExit as e:
                code = e.code
            finally:
                identity.fleet_name = saved
        lines = out.getvalue().strip().splitlines()
        ctx.check(f"exit 2 when the drawn name is this machine's ({'user@host' if '@studio' not in fake else 'user@studio'}), got {code}", code == 2)
        ctx.check("one line, the stop line, naming no real name", lines == [CI.STOP_LINE] and users[0] not in CI.STOP_LINE)


@test
def test_check_names_on_fake_machines(ctx: Ctx):
    ctx.check("a real user@host is caught", CI.check_names(["you@studio", "zed@buildbox"], ["zed"], "buildbox") == "zed@buildbox")
    ctx.check("a real user under a made-up host is caught", CI.check_names(["zed@studio"], ["zed"], "buildbox") == "zed@studio")
    ctx.check("a real host under a made-up user is caught", CI.check_names(["you@buildbox"], ["zed"], "buildbox") == "you@buildbox")
    ctx.check("the placeholder passes", CI.check_names(["you@studio", "you", "studio"], ["zed"], "buildbox") is None)
    ctx.check("on a Kali box (user and host `kali`, the fixtures' name) only kali@kali is caught",
              CI.check_names(["you@studio"], ["kali"], "kali") is None and CI.check_names(["kali@kali"], ["kali"], "kali") == "kali@kali")


@test
def test_the_dom_guard_fires_on_a_real_path_or_name(ctx: Ctx):
    users, host = ["zed"], "buildbox"
    for dom in ('<span title="C:\\Users\\someone\\AppData\\Local\\Temp\\shop">shop</span>', "<i>/home/someone/shop/basket.py</i>",
                "<b>C:/Users/someone/proj</b>", "<i>D:\\work\\zed\\shop</i>", "<td>zed@buildbox</td>", "<p>by zed</p>",
                "<p>BuildBox · online</p>"):
        out, code = io.StringIO(), None
        try:
            with contextlib.redirect_stdout(out):
                CI.guard(dom, "fleet", users, host)
        except SystemExit as e:
            code = e.code
        line = out.getvalue().strip()
        ctx.check(f"{dom!r} stops the tool with exit 1, got {code}", code == 1)
        ctx.check(f"the line names the page and masks the names, got {line!r}",
                  line.startswith("capture stopped: the fleet page carries") and "zed" not in line and "buildbox" not in line.lower())
    clean = ('<b>you@studio</b> · studio · <b>kali@lab</b> <span class="tm-runner">no runner</span> '
             '<a>zedVibes/Halo-Harness</a> <i>C:\\ProgramData\\halo-capture\\studio-1\\shop</i> <i>/tmp/orch-1/basket.py</i>')
    ctx.check(f"the fixtures' own names, a longer word and a neutral temp path pass, got {CI.leaks(clean, ['runner'], 'fv-az12')}",
              CI.leaks(clean, ["runner"], "fv-az12") == [] and CI.leaks(clean, ["kali"], "kali") == [] and CI.leaks(clean, ["zed"], "box") == [])
    ctx.check("a home path is one whoever's it is", [w for w, _ in CI.leaks("/home/x/work/x", ["runner"], "fv")][:1] == ["a home path"])


@test
def test_every_committed_studio_picture_is_a_tools_output(ctx: Ctx):
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / "tools").glob("*.py"))
    media = REPO / "docs" / "media"
    pics = sorted(p for p in media.iterdir() if p.suffix in (".png", ".gif") and (p.stem.startswith("studio-") or p.stem in ("hero", "social-preview")))
    ctx.check(f"the Studio pictures are there, got {len(pics)}", len(pics) >= 19)
    for p in pics:
        ctx.check(f"{p.name} is named by a tool under tools/", p.name in sources or f"{p.stem}.png" in sources)
        ctx.check(f"{p.name} is under 1 MB", p.stat().st_size < 1024 * 1024)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
