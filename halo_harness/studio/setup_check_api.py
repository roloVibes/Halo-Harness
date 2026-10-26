"""halo_harness.studio.setup_check_api -- the Check and Linux fixes routes of
Studio's Setup section (Halo 3.3.0.0 R3; docs/STUDIO-setup.md), reached from
studio/setup_api.dispatch_setup. Same loopback / origin / token guard as
every Studio route.

    POST setup/check {checks: [keys], models?: [refs]}
                         202 {job}: the ticked checks as one background job (studio/setup_check_job.py), each
                         check's frames streamed as `setup` frames on /api/events; 409 while one runs;
                         422 {error, problems} for an unknown key or no key; 422 {error, reason: "no_provider"}
                         when the guided first run is ticked and no provider is set (the start's own line)
    GET  setup/check     {job}: setup_check_job.current() -- the latest frame per check and the summary
    POST setup/check/stop  {stopping}
    POST setup/linux-fixes   the fixes this box is missing, applied as the wizard's Linux step applies them
                         (linux_fixes.install_static_ripgrep into ~/.local/bin, ensure_local_bin_on_rc)
                         -> 200 {...state, lines}; on Windows, or nothing missing: 200 "nothing to fix on this box"
"""

from __future__ import annotations


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def _state(req) -> dict:
    from halo_harness.studio.setup_state import setup_state
    return setup_state(req.cwd, req.state_dir)


def _strings(value) -> "list[str] | None":
    if not isinstance(value, list):
        return None
    return [str(v).strip() for v in value if isinstance(v, str) and v.strip()]


def post_check(req):
    from halo_harness.start import checks as C
    from halo_harness.studio import setup_check_job, start_job
    if setup_check_job.running():
        return 409, {"error": "a check is already running", "job": setup_check_job.current()}
    body = _body(req)
    keys = _strings(body.get("checks"))
    if not keys:
        return 422, {"error": "tick at least one check", "problems": [f"checks: a list of keys, from {', '.join(C.KEYS)}"]}
    unknown = [k for k in keys if k not in C.KEYS]
    if unknown:
        lines = [f"{k}: not a check (one of {', '.join(C.KEYS)})" for k in unknown]
        return 422, {"error": lines[0], "problems": lines}
    if "start" in keys:
        if start_job.running():
            return 409, {"error": "the guided first run is already running", "job": setup_check_job.current()}
        from halo_harness.start import fake
        if not fake.enabled():
            from halo_harness.start.provider import ready
            ok, text = ready()
            if not ok:
                return 422, {"error": text, "reason": "no_provider", "problems": [text]}
    models = _strings(body.get("models"))
    ctx = C.default_ctx(req.cwd, state_dir=req.state_dir, gym_models=models if models else None)
    return 202, {"job": setup_check_job.start(keys, ctx, req.state_dir, _publisher(req))}


def get_check(req):
    from halo_harness.studio import setup_check_job
    return 200, {"job": setup_check_job.current()}


def post_stop(req):
    from halo_harness.studio import setup_check_job
    return 200, {"stopping": setup_check_job.stop()}


def apply_fixes(items: list) -> "list[str]":
    """Apply each listed fix the way the wizard's Linux step does (tui/dialogs/init_wizard.py LinuxFixesStep)."""
    from halo_harness import linux_fixes as LF
    lines = []
    ids = {i.get("id") for i in items}
    if "ripgrep" in ids:
        from halo_harness.config.paths import home
        dest = home() / ".local" / "bin"  # the wizard's ~/.local/bin (a test's BRIDGE_TEST_HOME keeps it scoped)
        ok, msg = LF.install_static_ripgrep(dest)
        lines.append(f"installed rg: {msg}" if ok else f"rg was not installed: {msg}")
    if "path" in ids:
        written, path = LF.ensure_local_bin_on_rc()
        lines.append(f"added ~/.local/bin to PATH in {path}" if written else f"~/.local/bin is already on PATH in {path}")
    return lines


def post_linux_fixes(req):
    from halo_harness.studio import setup_check_state as S
    S.forget_linux()
    items = S.linux_items()
    if not items:
        return 200, {**_state(req), "lines": ["nothing to fix on this box"]}
    lines = apply_fixes(items)
    S.forget_linux()
    return 200, {**_state(req), "lines": lines}


ROUTES = {"setup/check": {"POST": post_check, "GET": get_check}, "setup/check/stop": {"POST": post_stop},
          "setup/linux-fixes": {"POST": post_linux_fixes}}


def dispatch_setup_check(req):
    """The answer for a route of this module, or None when the path is another module's."""
    methods = ROUTES.get(req.path)
    if methods is None:
        return None
    fn = methods.get(req.method)
    return fn(req) if fn else (405, {"error": "method not allowed"})
