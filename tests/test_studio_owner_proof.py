"""tests.test_studio_owner_proof -- the owner's page and a pack's key (Halo 3.3.14.0 R1, the November review's #4, #5,
#32, #33; studio/owner_proof.py, docs/STUDIO-shell.md "The owner's page and a pack's key"), over a real server:

1. #4: every write that changes what runs here (a pack's grant, enable, disable, install, sources, update, rollback,
   remove, service, settings, config; the bundles; Setup; Settings; sessions) is 403 "this needs the owner's own page"
   without `X-Halo-Owner`, and nothing changes; with the shell's proof the grant lands; reads need none.
2. #4: the page a browser navigates to carries the salt the proof is made of, a fetch or a frame of it does not; the
   shell reads it first (lib/owner.ts, main.tsx's first import) and sends the header from its own client only.
3. #5: a pack's key (`?k=`) opens a GET of that pack's own routes and nothing else: not a POST, not another pack's
   path, not a core route; the launch token in `?t=` is not taken on a pack GET; the registry names each key.
4. #32: `/` and `index.html` say `frame-ancestors 'self'` and `X-Frame-Options: SAMEORIGIN`.
5. #33: with HALO_STUDIO_LOG set, stderr never carries the token or a key.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.owner_rig import fetch  # noqa: E402
from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
UI = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui"
GATED = [("pack/install", {"source": "nowhere"}), ("pack/sources", {"add": "nowhere"}),
         ("pack/service-pack/enable", {"grant_all": True}), ("pack/service-pack/grant", {"need": "services"}),
         ("pack/service-pack/disable", {}), ("pack/service-pack/update", {"dry_run": True}),
         ("pack/service-pack/rollback", {}), ("pack/service-pack/remove", {}),
         ("pack/service-pack/service", {"name": "ticker", "verb": "start"}), ("pack/service-pack/settings", {"values": {}}),
         ("pack/service-pack/config", {"values": {"x": 1}}), ("pack/bundle/meta-glasses/on", {}),
         ("setup/config", {}), ("setup/done", {}), ("settings/set", {"key": "theme", "value": "midnight"}),
         ("sessions/new", {"cwd": "."}), ("sessions/abc/command", {"cmd": "pause"})]


@test
def test_the_owner_verbs_need_the_owners_proof(ctx: Ctx):
    from halo_harness.packs import state as S
    from halo_harness.studio.owner_proof import NEEDS_OWNER, needs_owner
    with PackStudio() as s:
        s.install_pack("service-pack", grants=[])
        for path, body in GATED:
            status, got, _h = s.call("POST", path, body, owner=False)
            ctx.check(f"POST {path} without the proof: 403 naming the owner's page, got {status} {got}",
                      status == 403 and got.get("error") == NEEDS_OWNER)
        rec = S.entry("service-pack", s.state) or {}
        ctx.check(f"nothing changed: still enabled, no grant, got {rec}", rec.get("enabled") is True and rec.get("granted") == [])
        status, got, _h = s.call("POST", "pack/service-pack/grant", {"need": "services"})
        ctx.check(f"the shell's own call (with the proof) grants, got {status}", status == 200
                  and S.granted("service-pack", S.load(s.state)) == ["services"])
        status, _got, _h = s.call("POST", "pack/service-pack/grant", {"need": "bash"}, owner=False)
        ctx.check("a wrong page cannot add bash after it", status == 403 and "bash" not in S.granted("service-pack", S.load(s.state)))
        for path in ("pack/registry", "pack/manager", "setup/state"):
            ctx.check(f"GET {path} needs no proof", s.call("GET", path, owner=False)[0] == 200)
        status, _r, _h = s.raw("/api/pack/service-pack/grant", method="POST", body={"need": "bash"}, owner=False,
                               token="wrong")
        ctx.check(f"a wrong token is still 401 first, got {status}", status == 401)
    ctx.check("a pack's own routes, a layout and a GET are not owner verbs",
              not needs_owner("POST", "packs/x/r/note") and not needs_owner("PUT", "layout/x:y")
              and not needs_owner("GET", "pack/x/grant") and needs_owner("DELETE", "settings/x"))


@test
def test_the_page_carries_the_salt_and_the_shell_sends_the_proof(ctx: Ctx):
    import hashlib
    import hmac
    from halo_harness.studio.owner_proof import header_for
    with PackStudio() as s:
        status, heads, page = fetch(s.base + "/")
        salt = s.srv.owner_salt
        ctx.check(f"a navigation's page carries data-owner-salt, got {status}",
                  status == 200 and f'data-owner-salt="{salt}"'.encode() in page)
        for dest in ("empty", "iframe", "object"):
            ctx.check(f"Sec-Fetch-Dest {dest}: the page without it", b"data-owner-salt" not in fetch(
                s.base + "/", headers={"Sec-Fetch-Dest": dest})[2])
        ctx.check("the proof is HMAC-SHA256(token, salt) as hex", header_for(s.srv) ==
                  hmac.new(s.token.encode(), salt.encode(), hashlib.sha256).hexdigest())
    main = (UI / "src" / "main.tsx").read_text(encoding="utf-8")
    owner = (UI / "src" / "lib" / "owner.ts").read_text(encoding="utf-8")
    api = (UI / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    ctx.check("main.tsx imports lib/owner first", main.lstrip().startswith('import "./lib/owner";'))
    ctx.check("owner.ts reads the salt and removes it", "dataset.ownerSalt" in owner and "delete root.dataset.ownerSalt" in owner)
    ctx.check("the shell's call sends X-Halo-Owner; plainCall does not", '"X-Halo-Owner": proof' in api and "request<T>(false" in api)
    packlib = "".join(p.read_text(encoding="utf-8") for p in (UI / "src" / "packlib").glob("*.ts"))
    ctx.check("no packlib module reaches the owner proof", "ownerHeader" not in packlib and "lib/owner" not in packlib
              and "plainCall" in packlib and "call<T>(true" not in packlib)
    dist = (UI.parent / "static" / "dist" / "studio.js").read_text(encoding="utf-8")
    ctx.check("the built shell carries it", "X-Halo-Owner" in dist and "ownerSalt" in dist)


@test
def test_a_packs_key_opens_its_own_gets_only(ctx: Ctx):
    from halo_harness.studio.owner_proof import raw_key
    with PackStudio() as s:
        s.install_pack("routes-pack", grants=["studio-routes"])
        key, other = s.key("routes-pack"), raw_key(s.token, "design")
        ping = s.base + "/api/packs/routes-pack/r/ping"
        status, _h, body = fetch(f"{ping}?k={key}")
        ctx.check(f"its key opens a GET of its routes, got {status} {body[:80]!r}", status == 200 and b'"routes-pack"' in body)
        ctx.check("the key never reaches the pack's handle", b'"k"' not in body)
        ctx.check("a POST with the key: 401", fetch(f"{ping}?k={key}", method="POST", data=b"{}")[0] == 401)
        ctx.check("another pack's key: 401", fetch(f"{ping}?k={other}")[0] == 401)
        for core in ("/api/state", "/api/pack/registry", "/api/pack/routes-pack/config", "/api/settings"):
            ctx.check(f"the key on {core}: refused", fetch(f"{s.base}{core}?k={key}")[0] in (401, 403))
        ctx.check("the launch token in ?t= on a pack GET: 401", fetch(f"{ping}?t={s.token}")[0] == 401)
        status, reg, _h = s.call("GET", "pack/registry")
        keys = {p["id"]: p.get("key") for p in reg.get("packs", [])}
        ctx.check(f"the registry names each running pack's key, got {sorted(keys)}", keys.get("routes-pack") == key)


@test
def test_the_shell_is_never_framed_by_another_page(ctx: Ctx):
    with PackStudio() as s:
        for path in ("/", "/index.html"):
            status, heads, _b = fetch(s.base + path)
            csp = heads.get("Content-Security-Policy", "")
            ctx.check(f"{path}: frame-ancestors 'self' and X-Frame-Options SAMEORIGIN, got {status} {csp!r}",
                      status == 200 and "frame-ancestors 'self'" in csp and heads.get("X-Frame-Options") == "SAMEORIGIN")


@test
def test_the_access_log_never_carries_the_token(ctx: Ctx):
    err = io.StringIO()
    with PackStudio() as s:  # its home scrubs HALO_* on the way in and puts them back on the way out
        s.install_pack("routes-pack", grants=["studio-routes"])
        key, token = s.key("routes-pack"), s.token
        os.environ["HALO_STUDIO_LOG"] = "1"
        try:
            with contextlib.redirect_stderr(err):
                fetch(f"{s.base}/api/packs/routes-pack/r/ping?k={key}&x=1")
                fetch(f"{s.base}/api/packs/routes-pack/r/ping?t={s.token}")
                fetch(f"{s.base}/api/events?t={s.token}&sessions=none", headers={"Origin": "http://evil.example"})
        finally:
            os.environ.pop("HALO_STUDIO_LOG", None)
    log = err.getvalue()
    ctx.check(f"the requests were logged, got {log[-300:]!r}", "k=...&x=1" in log and "t=..." in log)
    ctx.check("neither the token nor the key is in the log", token not in log and key not in log)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
