"""tests.test_packs_studio_api -- Studio's `/api/pack/...` (Halo 3.2.0.0 R3,
studio/packs_studio_api.py, studio/packs_studio_live.py,
fleet/pack_attention.py) over a real server and a scratch home:

1. `GET pack/registry`: the running packs' contributions with grant state;
   a disabled pack is not there; the token guard holds.
2. `GET pack/<id>/file/<path>`: a markdown or JSON file inside the pack's
   folder with the shell's CSP; `..`, an absolute path, a file type it does
   not serve and a disabled pack answer 404; the data folder's route.
3. The bundle: 403 naming the grant until studio-script is granted, then a
   JS module; through `?t=` without a header (an import()), a wrong token 403,
   an undeclared script 403.
4. `GET/POST pack/<id>/config`: the fields from config.schema; a good value
   lands in packs.settings.<id>, a bad one is 422 and nothing is written.
5. `pack_changed`: enable / disable in this process publish it at once; a
   change made elsewhere (state.json) is published by the watch.
6. A pack's attention rows: a row file of a declared kind is a
   `pack:<id>:<kind>` row with the pack's label and keys; A writes the
   answer file and removes the row; O opens the pack's section; an
   undeclared kind and a disabled pack's rows are not listed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio, next_kind, until  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_registry_route(ctx: Ctx):
    with PackStudio() as s:
        status, body, _ = s.call("GET", "pack/registry")
        ctx.check(f"no packs: an empty registry, got {status} {body}", status == 200 and body["packs"] == [] and "session" in body["core"])
        s.install_pack(grants=["hooks"])
        s.install_pack("studio-bundle")
        status, body, _ = s.call("GET", "pack/registry")
        ctx.check(f"both packs, got {[p['id'] for p in body['packs']]}", [p["id"] for p in body["packs"]] == ["doc-review", "studio-bundle"])
        ctx.check("grant state per pack", body["packs"][0]["script"] == "none" and body["packs"][1]["script"] == "not granted")
        status, _raw, _h = s.raw("/api/pack/registry", token="wrong")
        ctx.check(f"a wrong token is 401, got {status}", status == 401)
        from halo_harness.packs.grants import disable
        disable("doc-review")
        ctx.check("disabled: gone", [p["id"] for p in s.call("GET", "pack/registry")[1]["packs"]] == ["studio-bundle"])


@test
def test_files_inside_the_pack_only(ctx: Ctx):
    from halo_harness.studio.server import SHELL_CSP
    with PackStudio() as s:
        s.install_pack(grants=["hooks"])
        status, raw, headers = s.raw("/api/pack/doc-review/file/studio/notes.md")
        ctx.check(f"the markdown file, got {status}", status == 200 and raw.startswith(b"# Review notes"))
        ctx.check(f"its type and the shell's CSP, got {headers.get('Content-Type')}", headers.get("Content-Type", "").startswith("text/markdown")
                  and headers.get("Content-Security-Policy") == SHELL_CSP and headers.get("X-Content-Type-Options") == "nosniff")
        status, raw, headers = s.raw("/api/pack/doc-review/file/studio/checks.json")
        ctx.check("the JSON file", status == 200 and json.loads(raw)[0]["check"] == "links" and headers["Content-Type"].startswith("application/json"))
        outside = s.packs / "secret.md"
        outside.write_text("# not the pack's", encoding="utf-8")
        for path in ("/api/pack/doc-review/file/../secret.md", "/api/pack/doc-review/file/%2e%2e/secret.md",
                     f"/api/pack/doc-review/file/{outside.as_posix()}", "/api/pack/doc-review/file/hooks/note.py",
                     "/api/pack/doc-review/file/studio/nothing.md"):
            status, raw, _ = s.raw(path)
            ctx.check(f"{path}: 404, got {status} {raw[:120]!r}", status == 404 and b"not the pack's" not in raw)
        data = s.packs / ".data" / "doc-review"
        data.mkdir(parents=True)
        (data / "findings.json").write_text('[{"file": "README.md"}]', encoding="utf-8")
        status, raw, _ = s.raw("/api/pack/doc-review/data/findings.json")
        ctx.check(f"the data folder's route, got {status}", status == 200 and b"README.md" in raw)
        ctx.check("..out of the data folder: 404", s.raw("/api/pack/doc-review/data/../doc-review/pack.yaml")[0] == 404)
        from halo_harness.packs.grants import disable
        disable("doc-review")
        status, raw, _ = s.raw("/api/pack/doc-review/file/studio/notes.md")
        ctx.check(f"a disabled pack: 404, got {status} {raw!r}", status == 404 and b"runs here" in raw)


@test
def test_the_bundle_needs_its_grant(ctx: Ctx):
    from halo_harness.studio.server import SHELL_CSP
    with PackStudio() as s:
        s.install_pack("studio-bundle")
        path = "/api/pack/studio-bundle/file/studio/hello.js"
        status, raw, _ = s.raw(path)
        ctx.check(f"not granted: 403 naming the grant, got {status} {raw!r}", status == 403
                  and b"halo pack enable studio-bundle --grant studio-script" in raw)
        status, raw, _ = s.raw(path + "?t=" + s.token, auth=False)
        ctx.check("through ?t= too", status == 403)
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        enable(find("studio-bundle", cwd=s.repo), grant=["studio-script"])
        status, raw, headers = s.raw(path)
        ctx.check(f"granted: the module, got {status} {headers.get('Content-Type')}", status == 200
                  and headers.get("Content-Type", "").startswith("text/javascript") and b"export function mount" in raw)
        status, raw, headers = s.raw(path + "?t=" + s.token, auth=False)
        ctx.check(f"an import() (no header, ?t=): the module with the shell's CSP, got {status}", status == 200
                  and b"hello from" in raw and headers.get("Content-Security-Policy") == SHELL_CSP)
        ctx.check("a wrong ?t= is 403", s.raw(path + "?t=nope", auth=False)[0] == 403)
        ctx.check("no token at all is 401", s.raw(path, auth=False)[0] == 401)
        (s.packs / "studio-bundle" / "studio" / "other.js").write_text("export const x = 1;\n", encoding="utf-8")
        status, raw, _ = s.raw("/api/pack/studio-bundle/file/studio/other.js")
        ctx.check(f"a script no bundle panel names: 403, got {status} {raw!r}", status == 403 and b"not a bundle panel's source" in raw)


@test
def test_the_config_form_route(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack(grants=["hooks"])
        status, body, _ = s.call("GET", "pack/doc-review/config")
        fields = {f["key"]: f for f in body.get("fields", [])}
        ctx.check(f"the fields from config.schema, got {body}", status == 200 and list(fields) == ["style", "max_findings"]
                  and fields["style"]["enum"] == ["short", "long"] and fields["style"]["help"] == "How long the reviewer's notes are"
                  and fields["max_findings"]["value"] == 20 and body["key"] == "packs.settings.doc-review")
        status, body, _ = s.call("POST", "pack/doc-review/config", {"values": {"style": "long", "max_findings": 5}})
        cfg = json.loads((s.state / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"written to packs.settings.doc-review, got {status} {cfg.get('packs')}", status == 200
                  and cfg["packs"]["settings"]["doc-review"] == {"style": "long", "max_findings": 5} and body["values"]["style"] == "long")
        before = (s.state / "config.json").read_bytes()
        status, body, _ = s.call("POST", "pack/doc-review/config", {"values": {"style": "huge"}})
        ctx.check(f"a bad value: 422 naming the key, got {status} {body}", status == 422 and "style" in body["error"] and "short, long" in body["error"])
        ctx.check("and nothing written", (s.state / "config.json").read_bytes() == before)
        ctx.check("an empty body is 422", s.call("POST", "pack/doc-review/config", {})[0] == 422)
        ctx.check("a pack not here is 404", s.call("GET", "pack/nope/config")[0] == 404)


@test
def test_pack_changed_frames(ctx: Ctx):
    from halo_harness.studio import packs_studio_live as live
    saved = live.POLL_S
    live.POLL_S = 0.3
    try:
        with PackStudio() as s:
            s.install_pack("studio-bundle")
            s.call("GET", "pack/registry")  # the first read starts the watch
            q = s.frames()
            from halo_harness.packs.discover import find
            from halo_harness.packs.grants import disable, enable
            enable(find("studio-bundle", cwd=s.repo), grant=["studio-script"])
            f = next_kind(q, "pack_changed", 3.0)
            ctx.check(f"enable publishes pack_changed at once, got {f}", f is not None and f["data"] == {"why": "changed"} and f["session_id"] is None)
            disable("studio-bundle")
            ctx.check("disable too", next_kind(q, "pack_changed", 3.0) is not None)
            from halo_harness.packs import state as S
            rec = S.entry("studio-bundle", s.state)
            S.put("studio-bundle", {**rec, "enabled": True}, s.state)  # another process's write: no notify here
            ctx.check("a change made elsewhere: the watch publishes it", next_kind(q, "pack_changed", 4.0) is not None)
    finally:
        live.POLL_S = saved


def _row(s, kind: str, rid: str, what: str) -> Path:
    folder = s.packs / ".data" / "doc-review" / "attention"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{rid}.json"
    path.write_text(json.dumps({"kind": kind, "what": what, "detail": "two broken links"}), encoding="utf-8")
    return path


@test
def test_a_packs_attention_rows(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack(grants=["hooks"])
        row_file = _row(s, "review.ask", "readme", "README.md: 3 findings wait for you")
        _row(s, "review.other", "stray", "an undeclared kind")
        rows = []
        until(lambda: rows.extend(r for r in s.call("GET", "fleet/attention")[1]["rows"] if r["kind"].startswith("pack:")) or rows)
        ctx.check(f"one pack row (the undeclared kind left out), got {[r['kind'] for r in rows]}", [r["kind"] for r in rows] == ["pack:doc-review:review.ask"])
        row = rows[0] if rows else {"id": "", "keys": {}, "label": "", "what": "", "target": {}}
        ctx.check(f"the pack's label and keys, got {row}", row["label"] == "review" and row["keys"] == {"a": "accept", "r": "redo", "s": "skip", "o": "open"}
                  and row["what"] == "README.md: 3 findings wait for you" and row["agent"] == "pack doc-review")
        status, got, _ = s.call("POST", "fleet/attention/answer", {"id": row["id"], "key": "o"})
        ctx.check(f"O opens the pack's section, got {got}", status == 200 and got.get("open", {}).get("section") == "doc-review--docs")
        status, got, _ = s.call("POST", "fleet/attention/answer", {"id": row["id"], "key": "a"})
        answer = s.packs / ".data" / "doc-review" / "answers" / "readme.json"
        ctx.check(f"A answers it, got {status} {got}", status == 200 and got.get("answer") == "accept" and got["result"]["answered"] is True)
        note = json.loads(answer.read_text(encoding="utf-8")) if answer.is_file() else {}
        ctx.check(f"the answer file for the pack's code, got {note}", note.get("key") == "a" and note.get("answer") == "accept"
                  and note.get("kind") == "review.ask" and note.get("row") == "readme")
        ctx.check("the row file is gone", not row_file.exists())
        _row(s, "review.ask", "later", "another")
        ctx.check("a new row lands", until(lambda: any(r["kind"].startswith("pack:") for r in s.call("GET", "fleet/attention")[1]["rows"])))
        from halo_harness.packs.grants import disable
        disable("doc-review")
        ctx.check("disabled: its rows are not listed",
                  until(lambda: not any(r["kind"].startswith("pack:") for r in s.call("GET", "fleet/attention")[1]["rows"])))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
