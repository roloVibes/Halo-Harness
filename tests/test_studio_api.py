"""tests.test_studio_api -- `halo studio`'s server and routes (Halo 2.1.0
round B3): an in-process server on a random port over a scoped home; the
loopback/token/origin guard; every read route; create, save, validate (422
with the validator's lines), 409 on a shipped file, layout persistence,
apply (writes the same config `halo teams use` does), delete; the static
page and its security headers.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Studio:
    """A Studio over a state dir of its own: `BRIDGE_STATE_DIR` points at a
    fresh folder for the fixture's lifetime (and is put back after), so an
    earlier module's copy-on-first-use of the shipped lineups into the shared
    scratch home can never turn a shipped lineup into a user one here."""

    def __enter__(self):
        from halo_harness.studio.server import start_server
        self._saved = os.environ.get("BRIDGE_STATE_DIR")
        root = Path(tempfile.mkdtemp(prefix="studio-api-"))
        self.state = root / ".halo"
        self.state.mkdir()
        os.environ["BRIDGE_STATE_DIR"] = str(self.state)
        self.srv = start_server(port=0, cwd=self.state.parent / "proj", state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()
        if self._saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self._saved

    def call(self, method, path, body=None, *, token=None, origin=None, raw=False):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (self.srv.token if token is None else token))
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if origin:
            req.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, (r.read() if raw else json.loads(r.read() or b"{}")), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


@test
def test_guard_token_origin_and_static(ctx: Ctx):
    with _Studio() as s:
        status, body, headers = s.call("GET", "/", raw=True)
        ctx.check("the page is served", status == 200 and b"<title>Halo Studio</title>" in body)
        ctx.check("the page carries a content-security policy and nosniff",
                  "default-src 'self'" in headers.get("Content-Security-Policy", "") and headers.get("X-Content-Type-Options") == "nosniff")
        ctx.check("every static file the page names is served",
                  all(s.call("GET", "/legacy/" + f, raw=True)[0] == 200 for f in ("studio.css", "api.js", "canvas.js", "inspector.js", "bio-form.js", "palette.js", "app.js")))
        ctx.check("a path outside static is refused", s.call("GET", "/../server.py", raw=True)[0] == 404)
        ctx.check("no token is a 401", s.call("GET", "/api/state", token="")[0] == 401)
        ctx.check("a wrong token is a 401", s.call("GET", "/api/state", token="nope")[0] == 401)
        ctx.check("a foreign origin is a 403", s.call("GET", "/api/state", origin="http://evil.example")[0] == 403)
        ctx.check("the server's own origin passes", s.call("GET", "/api/state", origin=s.base)[0] == 200)
        ctx.check("an unknown route is a 404", s.call("GET", "/api/nope")[0] == 404)
        ctx.check("a wrong method is a 405", s.call("DELETE", "/api/state")[0] == 405)


@test
def test_read_routes(ctx: Ctx):
    with _Studio() as s:
        status, st, _ = s.call("GET", "/api/state")
        ctx.check("state names the version, the shipped lineups and the top sections",
                  status == 200 and st["version"] and "balanced" in st["shipped_lineups"] and "delegation" in st["top_sections"])
        status, ls, _ = s.call("GET", "/api/lineups")
        ctx.check("the six shipped lineups are listed with their agent counts",
                  status == 200 and {l["name"] for l in ls} >= {"balanced", "code-review", "halo-dev-cycle", "local-first", "quality", "standard"}
                  and all(l["agents"] >= 1 for l in ls))
        status, lp, _ = s.call("GET", "/api/lineup/halo-dev-cycle")
        nodes, edges = lp["graph"]["nodes"], lp["graph"]["edges"]
        ctx.check("halo-dev-cycle has seven nodes, one main, delegation edges from it and pipeline edges",
                  status == 200 and len(nodes) == 7 and sum(n["role"] == "main" for n in nodes) == 1
                  and sum(e["kind"] == "delegation" for e in edges) == 6 and any(e["kind"] == "pipeline" for e in edges))
        ctx.check("delegation edges carry the routing keys", any("implement" in e["label"] for e in edges if e["kind"] == "delegation"))
        ctx.check("every node resolves a model and names its bio's scope", all(n["model"] and n["scope"] for n in nodes))
        ctx.check("the payload carries raw, yaml, a role table, notes and sections",
                  lp["raw"]["name"] == "halo-dev-cycle" and "agents:" in lp["yaml"] and isinstance(lp["role_table"], dict)
                  and isinstance(lp["notes"], list) and "delegation" in lp["sections"])
        status, bs, _ = s.call("GET", "/api/bios")
        ctx.check("bios list the shipped bios with model and kind", status == 200 and any(b["name"] == "reviewer" for b in bs))
        status, b, _ = s.call("GET", "/api/bio/reviewer")
        ctx.check("a bio payload carries raw, resolved, yaml and no problems", status == 200 and b["raw"]["name"] == "reviewer" and b["problems"] == [])
        ctx.check("models answers a list (empty on a bare home)", s.call("GET", "/api/models")[0] == 200)
        ctx.check("session answers running as a bool and an agents list", isinstance(s.call("GET", "/api/session")[1]["running"], bool) and isinstance(s.call("GET", "/api/session")[1]["agents"], list))
        ctx.check("tools answers names", "Bash" in s.call("GET", "/api/tools")[1])


@test
def test_write_routes(ctx: Ctx):
    from halo_harness.theme import get_config_value
    with _Studio() as s:
        status, body, _ = s.call("PUT", "/api/lineup/balanced", {"raw": {"name": "balanced", "agents": []}})
        ctx.check("saving a shipped lineup without duplicate is a 409", status == 409 and "duplicate" in body["error"])
        status, new, _ = s.call("POST", "/api/lineup", {"name": "studio-t", "from": "balanced"})
        ctx.check("a new lineup from a shipped one lands in user scope", status == 201 and new["scope"] == "user" and Path(new["path"]).is_file())
        raw = new["raw"]
        raw["description"] = "studio edit"
        status, saved, _ = s.call("PUT", "/api/lineup/studio-t", {"raw": raw})
        ctx.check("a valid save round-trips through the validator", status == 200 and saved["raw"]["description"] == "studio edit")
        status, bad, _ = s.call("PUT", "/api/lineup/studio-t", {"yaml": "name: studio-t\nagents: [{agent: nope, role: main}]\n"})
        ctx.check("an invalid save is a 422 with the validator's lines and leaves the file alone",
                  status == 422 and any("nope" in p for p in bad["problems"])
                  and s.call("GET", "/api/lineup/studio-t")[1]["raw"]["description"] == "studio edit")
        status, bad, _ = s.call("PUT", "/api/lineup/studio-t", {"yaml": "- not: a mapping\n"})
        ctx.check("YAML that is not a mapping is a 422", status == 422)
        status, v, _ = s.call("POST", "/api/validate", {"kind": "lineup", "raw": raw})
        ctx.check("validate returns problems and a graph without writing", status == 200 and v["problems"] == [] and v["graph"]["nodes"])
        s.call("PUT", "/api/layout/studio-t", {"positions": {"main#0": {"x": 10, "y": 20}}})
        ctx.check("a layout persists", s.call("GET", "/api/layout/studio-t")[1] == {"main#0": {"x": 10, "y": 20}})
        status, ap, _ = s.call("POST", "/api/lineup/studio-t/apply")
        ctx.check("apply writes team and roles like halo teams use",
                  status == 200 and ap["active_team"] == "studio-t" and get_config_value("team", "") == "studio-t"
                  and get_config_value("roles.enabled", None) is True)
        ctx.check("lineups now mark it active", any(l["name"] == "studio-t" and l["active"] for l in s.call("GET", "/api/lineups")[1]))
        status, nb, _ = s.call("POST", "/api/bio", {"name": "studio-bio", "from": "general"})
        ctx.check("a new bio from a shipped one is created", status == 201 and nb["scope"] == "user")
        braw = nb["raw"]
        braw["models"] = {"preference": "or:vendor/model"}
        status, sb, _ = s.call("PUT", "/api/bio/studio-bio", {"raw": braw})
        ctx.check("a bio save round-trips", status == 200 and sb["raw"]["models"]["preference"] == "or:vendor/model")
        status, bad, _ = s.call("PUT", "/api/bio/studio-bio", {"raw": {"name": "studio-bio", "kind": "not-a-kind"}})
        ctx.check("a bad bio is a 422", status == 422 and bad["problems"])
        ctx.check("deleting a shipped bio is a 409", s.call("DELETE", "/api/bio/general")[0] == 409)
        ctx.check("deleting the user bio and lineup works",
                  s.call("DELETE", "/api/bio/studio-bio")[0] == 200 and s.call("DELETE", "/api/lineup/studio-t")[0] == 200)
        ctx.check("a bad name is a 422", s.call("POST", "/api/lineup", {"name": "bad name!"})[0] == 422)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio api tests"))
