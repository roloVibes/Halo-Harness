"""tests.test_studio_dist -- Halo 3.0.3.0 round R3: the React shell's committed
build. static/dist holds index.html + studio.js + studio.css (stable names,
no remote URL anywhere); `GET /` serves it under a CSP without
'unsafe-inline'; 3.0.7.0 R2: the classic page (/legacy/) is gone, and a
checkout without a build answers `/` with one line saying how to build the
UI; the UI sources stay under 250 lines a file; the package.json has no
runtime dependency beyond react/react-dom and pins exact versions; the
wheel's package-data names dist (and no longer legacy).

CI's studio-ui job runs this after `npm run build` and the drift check.
Run: python tests/test_studio_dist.py
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
STUDIO = REPO / "halo_harness" / "studio"
DIST = STUDIO / "static" / "dist"
UI = STUDIO / "ui"


class _Studio:
    def __enter__(self):
        from halo_harness.studio.server import start_server
        state = Path(tempfile.mkdtemp(prefix="studio-dist-")) / ".halo"
        state.mkdir()
        self.srv = start_server(port=0, cwd=state.parent, state_dir=state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)


@test
def test_dist_exists_with_stable_names_and_no_remote_url(ctx: Ctx):
    for name in ("index.html", "studio.js", "studio.css"):
        ctx.check(f"static/dist/{name} exists", (DIST / name).is_file())
    page = (DIST / "index.html").read_text(encoding="utf-8")
    ctx.check("index.html loads ./studio.js and ./studio.css", 'src="./studio.js"' in page and 'href="./studio.css"' in page)
    files = [p for p in DIST.rglob("*") if p.is_file()]
    hits = [p.name for p in files if re.search(rb"https?://", p.read_bytes())]
    ctx.check(f"no http:// or https:// in any dist file, got {hits}", files and not hits)
    ctx.check("no source maps are shipped", not any(p.suffix == ".map" for p in files))
    attrs = (REPO / ".gitattributes").read_text(encoding="utf-8")
    ctx.check(".gitattributes keeps the dist LF", "halo_harness/studio/static/dist/* text eol=lf" in attrs)


@test
def test_root_serves_the_shell_and_nothing_else(ctx: Ctx):
    with _Studio() as s:
        status, body, headers = s.get("/")
        csp = headers.get("Content-Security-Policy", "")
        ctx.check("GET / is the shell", status == 200 and b'id="root"' in body and b"studio.js" in body)
        ctx.check(f"the shell's CSP is strict, got {csp!r}", "default-src 'self'" in csp and "connect-src 'self'" in csp
                  and "unsafe-inline" not in csp)
        ctx.check("GET /index.html is the same page", s.get("/index.html")[1] == body)
        st, js, h = s.get("/studio.js")
        ctx.check("studio.js is served as JavaScript", st == 200 and "javascript" in h.get("Content-Type", "") and len(js) > 1000)
        ctx.check("3.0.7.0 R2: /legacy/ is gone", s.get("/legacy/index.html")[0] == 404 and s.get("/legacy/")[0] == 404)
        ctx.check("a path out of dist is a 404", s.get("/../server.py")[0] == 404 and s.get("/%2e%2e/server.py")[0] == 404)
        ctx.check("an unknown file is a 404", s.get("/nope.js")[0] == 404)


@test
def test_without_a_build_root_says_how_to_build_it(ctx: Ctx):
    from halo_harness.studio import server
    saved = server.DIST
    server.DIST = Path(tempfile.mkdtemp(prefix="no-dist-")) / "dist"
    try:
        with _Studio() as s:
            status, body, headers = s.get("/")
            ctx.check("GET / is one line saying how to build the UI", status == 200 and b"npm run build" in body and b"<script" not in body)
            ctx.check("with the shell's strict CSP", "unsafe-inline" not in headers.get("Content-Security-Policy", ""))
            ctx.check("anything else is a 404", s.get("/studio.js")[0] == 404 and s.get("/app.js")[0] == 404)
    finally:
        server.DIST = saved


@test
def test_url_for_the_shell(ctx: Ctx):
    from halo_harness.studio import server
    from halo_harness.studio.launch import url_from_info
    with _Studio() as s:
        ctx.check("the shell URL is / with the token fragment", server.url_for(s.srv, "design").endswith(f"/?mode=design#t={s.srv.token}"))
    ctx.check("a reused Studio's URL", url_from_info({"port": 4, "token": "x"}, "roles") == "http://127.0.0.1:4/?mode=roles#t=x")
    import io
    from contextlib import redirect_stderr, redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            server.cmd_studio(["--help"])
        except SystemExit:
            pass
    ctx.check("3.0.7.0 R2: `halo studio --help` has no --legacy any more", "--mode" in buf.getvalue() and "--legacy" not in buf.getvalue())


@test
def test_ui_sources_stay_small_and_dependencies_minimal(ctx: Ctx):
    src = [p for p in (UI / "src").rglob("*") if p.suffix in (".ts", ".tsx", ".css")]
    ctx.check("the UI has sources", len(src) >= 20)
    long = [f"{p.relative_to(UI)}={n}" for p in src if (n := len(p.read_text(encoding="utf-8").splitlines())) > 250]
    ctx.check(f"every ui/src file is at most 250 lines, over: {long}", not long)
    pkg = json.loads((UI / "package.json").read_text(encoding="utf-8"))
    ctx.check(f"runtime deps are react and react-dom only, got {sorted(pkg.get('dependencies', {}))}",
              sorted(pkg.get("dependencies", {})) == ["react", "react-dom"])
    dev = pkg.get("devDependencies", {})
    ctx.check("dev deps are the toolchain only", set(dev) <= {"typescript", "vite", "@vitejs/plugin-react", "@types/react", "@types/react-dom"})
    pins = {**pkg.get("dependencies", {}), **dev}
    ctx.check(f"every version is exact, got {pins}", all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in pins.values()))
    ctx.check("package-lock.json is committed beside it", (UI / "package-lock.json").is_file())
    ctx.check(".nvmrc names the node major", (UI / ".nvmrc").read_text(encoding="utf-8").strip() in ("22", "24"))
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    ctx.check("node_modules is ignored", "node_modules/" in ignore)


@test
def test_wheel_package_data_names_dist_only(ctx: Ctx):
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    ctx.check("package-data has studio/static/dist/*", '"studio/static/dist/*"' in text)
    ctx.check("package-data no longer names studio/static/legacy", "studio/static/legacy" not in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio dist tests"))
