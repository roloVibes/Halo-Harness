"""tests.test_local_hf_api -- Halo 3.3.5.0 R5: studio/local_hf_api.py + local_server_api.py through studio/api.dispatch
on tests/helpers/hf_local_env.HfHome (one model folder, the fake hub on 127.0.0.1:0, the fake llama-server as
huggingface.llama_server_bin, box's card from the seam). No real hub, no real server, no model call:

1. the folders: GET local/hf/dirs, POST local/hf/dirs adds one (config written, its cli line), forget, a non-folder 422;
2. download: 422 with the licence line until accept, then a job to on-disk; a gated repo without HF_TOKEN 422
   needs_token, with it the file; an unknown repo 404; a folder that is not a model folder 422;
3. the Library: a hub row and its file say "on disk" in the folder after the download;
4. serve: dry = the flags and where each comes from; then ready; GET local/servers, the Hosts card (managed server,
   Stop), the Models host with `hf:local/<model>`, status, the log; the folder row served with its ref;
5. delete: 409 while served; stop; 422 with the uses card while a role names `hf:local/<model>`; force deletes the
   files and the repo folder; a stop of a server Halo did not start 404s and says so.
Run: python -m tests.test_local_hf_api
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import GATED, GGUF, MLX, TOKEN, HfHome  # noqa: E402
from tests.helpers.mock_hub import gguf_bytes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _download(h, repo, file=""):
    s, v = h.api("POST", "local/hf/download", {"repo": repo, "file": file, "accept": True})
    return s, v, (h.wait_job(v["job"]) if s == 200 else {})


@test
def test_the_folders(ctx: Ctx):
    with HfHome() as h:
        s, d = h.api("GET", "local/hf/dirs")
        ctx.check(f"one folder, empty, box's card, got {s} {d['dirs']} {d['host']}", s == 200 and len(d["dirs"]) == 1
                  and d["dirs"][0]["exists"] and d["host"] == "box" and d["window"] == 32768)
        other = h.root / "more-models"
        other.mkdir()
        s, a = h.api("POST", "local/hf/dirs", {"path": str(other)})
        ctx.check(f"added, its cli line, got {s} {a}", s == 200 and a["cli"] == f"halo local add {other}"
                  and len(h.config()["huggingface"]["model_dirs"]) == 2)
        ctx.check("a second add 422s", h.api("POST", "local/hf/dirs", {"path": str(other)})[0] == 422)
        ctx.check("a non-folder 422s", h.api("POST", "local/hf/dirs", {"path": str(h.root / "nope")})[0] == 422)
        s, f = h.api("POST", "local/hf/forget", {"path": str(other)})
        ctx.check(f"forgotten, got {s} {f}", s == 200 and len(h.config()["huggingface"]["model_dirs"]) == 1 and other.is_dir())


@test
def test_download_licence_first_gated_and_errors(ctx: Ctx):
    with HfHome() as h:
        s, v = h.api("POST", "local/hf/download", {"repo": GGUF, "file": "Tiny-1B-Q8_0.gguf"})
        ctx.check(f"422 with the licence line until accept, got {s} {v.get('error')} {v.get('cli')}",
                  s == 422 and v["needs_accept"] and "licence apache-2.0" in v["error"] and h.hub.resolves() == []
                  and v["cli"] == f"halo local download {GGUF} Tiny-1B-Q8_0.gguf --dir {h.models} --yes")
        s, v, end = _download(h, GGUF, "Tiny-1B-Q8_0.gguf")
        ctx.check(f"accepted: a job to on disk, got {s} {end.get('say')}", s == 200 and end.get("ok") and "on disk" in end["say"])
        s, g = h.api("POST", "local/hf/download", {"repo": GATED, "accept": True})
        ctx.check(f"gated, no token: 422 needs_token, got {s} {g.get('error')}", s == 422 and g["needs_token"] and "HF_TOKEN" in g["error"]
                  and "gated (manual)" in g["error"])
        os.environ["HF_TOKEN"] = TOKEN
        s, g, end = _download(h, GATED)
        ctx.check(f"with HF_TOKEN: the file, got {s} {end.get('say')}", s == 200 and end.get("ok")
                  and h.hub.resolves()[-1]["auth"] == f"Bearer {TOKEN}")
        os.environ.pop("HF_TOKEN")
        ctx.check("an unknown repo 404s", h.api("POST", "local/hf/download", {"repo": "nobody/none", "accept": True})[0] == 404)
        s, x = h.api("POST", "local/hf/download", {"repo": GGUF, "dir": str(h.root), "accept": True})
        ctx.check(f"a folder not on the list 422s, got {s} {x.get('error')}", s == 422 and "halo local add" in x["error"])
        ctx.check("422 without a repo", h.api("POST", "local/hf/download", {})[0] == 422)


@test
def test_the_library_says_on_disk(ctx: Ctx):
    with HfHome() as h:
        repo, f = "unsloth/Qwen3.8-27B-GGUF", "Qwen3.8-27B-Q4_0.gguf"
        h.hub.add(repo, {f: gguf_bytes(120_000, "u")})
        _download(h, repo, f)
        rows = h.api("GET", f"local/library/hf/{repo}")[1]["rows"]
        mine = next((r for r in rows if r["tag_or_file"] == f), {})
        others = [r for r in rows if r["tag_or_file"] != f]
        ctx.check(f"the file row is on disk in the folder, got {mine.get('on_disk')}", mine.get("on_disk") == [str(h.models)])
        ctx.check("the other files are not", others and all(r["on_disk"] == [] for r in others))
        lib = h.api("GET", "local/library", query={"source": "hf", "q": "Qwen3.8-27B"})[1]["rows"]
        hit = next((r for r in lib if r["id"] == repo), {})
        ctx.check(f"the repo row too, got {hit.get('on_disk')}", hit.get("on_disk") == [str(h.models)])


@test
def test_serve_hosts_models_status_log(ctx: Ctx):
    with HfHome() as h:
        _download(h, GGUF, "Tiny-1B-Q4_K_M.gguf")
        path = h.api("GET", "local/hf/dirs")[1]["dirs"][0]["models"][0]["path"]
        s, dry = h.api("POST", "local/hf/serve", {"path": path, "dry": True})
        ctx.check(f"dry: the flags and their sources, got {s} {dry.get('flags')} {dry.get('sources', {}).get('window')}",
                  s == 200 and dry["flags"]["window"] == 40960 and dry["flags"]["ngl"] == 37 and "box" in dry["sources"]["window"]
                  and "-ngl" in dry["argv"] and dry["cli"] == f"halo local serve {path}" and dry["ref"] == "hf:local/Tiny-1B-Q4_K_M")
        s, srv = h.api("POST", "local/hf/serve", {"path": path})
        ctx.check(f"started and ready, got {s} {srv.get('say')}", s == 200 and srv["ready"] and srv["stop_cli"] == f"halo local stop {srv['id']}")
        listed = h.api("GET", "local/servers")[1]["servers"]
        ctx.check(f"local/servers lists it, got {listed}", [x["id"] for x in listed] == [srv["id"]] and listed[0]["alive"])
        cards = h.api("GET", "local/hosts")[1]["hosts"]
        card = next((c for c in cards if c["name"] == srv["id"]), {})
        ctx.check(f"a Hosts card, got {card.get('source')} {card.get('kind')} {card.get('managed', {}).get('port')}",
                  card.get("source") == "managed server" and card["kind"] == "llama-server" and card["managed"]["port"] == srv["port"]
                  and card["controls"]["ok"] and card["models"] == ["Tiny-1B-Q4_K_M"])
        mh = next((x for x in h.api("GET", "local/models")[1]["hosts"] if x["name"] == srv["id"]), {})
        ctx.check(f"a Models host with hf:local/<model>, got {mh}", [m["ref"] for m in mh.get("models") or []] == ["hf:local/Tiny-1B-Q4_K_M"])
        st = h.api("GET", f"local/server/{srv['id']}/status")[1]
        ctx.check(f"status, got {st}", st["ready"] and st["slots"])
        lg = h.api("GET", f"local/server/{srv['id']}/log", query={"n": "10"})[1]
        ctx.check(f"the log's tail, got {lg.get('lines')}", lg["ok"] and len(lg["lines"]) <= 10 and lg["cli"] == f"halo local log {srv['id']} -n 10")
        row = h.api("GET", "local/hf/dirs")[1]["dirs"][0]["models"][0]
        ctx.check(f"the folder row is served with its ref, got {row['served']} {row['ref']}",
                  row["ref"] == "hf:local/Tiny-1B-Q4_K_M" and row["served"][0]["port"] == srv["port"])


@test
def test_delete_409_uses_card_force_and_not_ours(ctx: Ctx):
    with HfHome() as h:
        _download(h, GGUF, "Tiny-1B-Q4_K_M.gguf")
        path = h.api("GET", "local/hf/dirs")[1]["dirs"][0]["models"][0]["path"]
        srv = h.api("POST", "local/hf/serve", {"path": path})[1]
        s, d = h.api("POST", "local/hf/delete", {"path": path, "force": True})
        ctx.check(f"409 while served, got {s} {d.get('error')}", s == 409 and srv["id"] in d["error"])
        s, st = h.api("POST", f"local/server/{srv['id']}/stop")
        ctx.check(f"stopped, got {s} {st.get('say')}", s == 200 and st["ok"])
        cfg = h.config()
        cfg["roles"] = {"reviewer": "hf:local/Tiny-1B-Q4_K_M"}
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        s, u = h.api("GET", "local/hf/uses", query={"path": path})
        ctx.check(f"the uses card, got {u.get('uses', {}).get('line')}", s == 200 and u["uses"]["roles"] == ["reviewer"])
        s, d = h.api("POST", "local/hf/delete", {"path": path})
        ctx.check(f"422 with the uses card, got {s} {d.get('error')}", s == 422 and "`reviewer` role" in d["error"]
                  and d["cli"] == f"halo local rm {path} --force")
        s, d = h.api("POST", "local/hf/delete", {"path": path, "force": True})
        repo_dir = h.models / f"models--{GGUF.replace('/', '--')}"
        ctx.check(f"force deletes it and the repo folder, got {s} {d.get('say')}", s == 200 and not Path(path).exists() and not repo_dir.exists())
        ctx.check("the folder is empty again", h.api("GET", "local/hf/dirs")[1]["dirs"][0]["models"] == [])
        s, n = h.api("POST", "local/server/llama-1/stop")
        ctx.check(f"a server Halo did not start: 404, said why, got {s} {n.get('error')}", s == 404 and "did not start" in n["error"])
        ctx.check("delete of a path not listed 404s", h.api("POST", "local/hf/delete", {"path": str(h.root / 'x.gguf')})[0] == 404)
        _download(h, MLX)
        mrow = next(r for r in h.api("GET", "local/hf/dirs")[1]["dirs"][0]["models"] if r["kind"] == "mlx")
        ctx.check(f"an MLX folder is named by its repo, got {mrow['model']} {mrow['repo']}", mrow["model"] == "Tiny-4bit" and mrow["repo"] == MLX)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
