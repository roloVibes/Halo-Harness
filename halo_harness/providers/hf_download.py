"""halo_harness.providers.hf_download -- Halo 3.3.5.0 R5: a Hugging Face repo, or one file of it, downloaded into a
`huggingface.model_dirs` folder through the hub cache's own layout (providers/huggingface_hub_cache.py):

    <dir>/models--<org>--<name>/blobs/<sha256 or blob id>.part   the bytes while they move (a cancel keeps it)
    <dir>/models--<org>--<name>/snapshots/<commit>/<file>         the finished file
    <dir>/models--<org>--<name>/refs/main                         the commit

    prepare(repo, file=None, *, token=None) -> plan   the repo's info (`/api/models/<repo>?blobs=true`): the files
        picked, their sizes and checksums, the commit, and the licence line -- read BEFORE any byte moves, so the
        route and the CLI show it and ask first
    download(repo, file=None, *, dest_dir, token, on_status, cancel, plan=None) -> result

Each file is `GET <hub>/<repo>/resolve/main/<file>` through providers/http.urlopen_tls, streamed to its `.part`; a
part already there resumes with `Range: bytes=<have>-` (a 200, not a 206, starts it again). The bytes are checked
against the listing (an LFS file's `lfs.sha256`, a small file's `blobId`, the git blob sha1); a mismatch removes the
part. `on_status` gets the pull job's `{status, digest: <file>, total, completed}`; `cancel` (an Event) keeps the
part. The files: the one named (a GGUF quant's shards together; a quant word picks its group), else every file of an
MLX repo, else a GGUF repo's one quant (PREFERRED). A gated repo needs HF_TOKEN. The hub is `HF_ENDPOINT` or
huggingface.co; under BRIDGE_TEST_NO_BACKGROUND_NET only a loopback hub (tests/helpers/mock_hub.py) is read."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

HUB = "https://huggingface.co"
CHUNK = 1 << 20
TIMEOUT_S = 30
USER_AGENT, SKIP_WHOLE = "halo-harness (local models download)", (".gitattributes",)
PREFERRED = ("Q4_K_M", "Q4_K_S", "UD-Q4_K_XL", "Q5_K_M", "Q4_0", "IQ4_XS", "Q6_K", "Q8_0")


class HubError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message


def hub_base() -> str:
    return (os.environ.get("HF_ENDPOINT") or HUB).rstrip("/")


def _check(base: str) -> None:
    from halo_harness.config.paths import background_net_disabled
    host = urllib.parse.urlparse(base).hostname or ""
    if background_net_disabled() and host not in ("127.0.0.1", "localhost", "::1"):
        raise HubError("blocked", "the hub is not read under the test flag (BRIDGE_TEST_NO_BACKGROUND_NET): "
                       "HF_ENDPOINT names a loopback fake")


def _open(url: str, headers: Optional[dict] = None):
    from halo_harness.providers.http import urlopen_tls
    _check(url)
    return urlopen_tls(urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})}), timeout=TIMEOUT_S)


def _auth(token: Optional[str]) -> dict:  # the token goes to the hub only (a cross-host redirect drops it)
    return {"Authorization": f"Bearer {token}"} if token else {}


def repo_dir(dest_dir, repo: str) -> Path:
    return Path(dest_dir) / ("models--" + repo.replace("/", "--"))


def repo_info(repo: str, token: Optional[str] = None) -> dict:
    url = f"{hub_base()}/api/models/{urllib.parse.quote(repo, safe='/')}?blobs=true"
    for hdr in ({}, _auth(token)) if token else ({},):
        try:
            with _open(url, hdr) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 404) and not hdr and token:
                continue  # a private repo answers only with the token
            raise HubError("missing" if e.code == 404 else "http", f"the hub answered {e.code} for {repo}") from None
        except Exception as e:
            if isinstance(e, HubError):
                raise
            raise HubError("unreachable", f"the hub did not answer for {repo}: {str(e) or type(e).__name__}") from None
    raise HubError("missing", f"the hub has no repo {repo} (or it is private and the token cannot read it)")


def licence(info: dict, repo: str) -> dict:
    card = info.get("cardData") if isinstance(info.get("cardData"), dict) else {}
    lic = card.get("license") or next((t.split(":", 1)[1] for t in info.get("tags") or []
                                       if isinstance(t, str) and t.startswith("license:")), "") or ""
    gated = info.get("gated") or False
    line = f"{repo}: licence {lic or 'not stated on the repo card'}"
    if gated:
        line += (f"; gated ({gated}): the repo asks you to accept its terms on huggingface.co/{repo} first, then "
                 "HF_TOKEN reads its files")
    return {"license": lic, "gated": gated, "line": line, "prompt": str(card.get("extra_gated_prompt") or "").strip()[:400]}


def _quant(name: str) -> str:
    from halo_harness.models_library.hf_hub import quant_of_file
    return quant_of_file(name)


def _row(s: dict) -> dict:
    lfs = s.get("lfs") if isinstance(s.get("lfs"), dict) else {}
    return {"name": str(s.get("rfilename")), "size": s.get("size") if isinstance(s.get("size"), int) else lfs.get("size"),
            "sha256": lfs.get("sha256"), "blob_id": s.get("blobId")}


def pick_files(info: dict, file: Optional[str] = None) -> "tuple[list, str]":
    """(the files to fetch, the kind gguf | mlx | safetensors)."""
    from halo_harness.models_library.hf_hub import SHARD, SKIP
    sib = [s for s in info.get("siblings") or [] if isinstance(s, dict) and s.get("rfilename")]
    ggufs = [s for s in sib if str(s["rfilename"]).lower().endswith(".gguf")]
    kind = "gguf" if ggufs else "mlx" if "mlx" in (info.get("tags") or []) else "safetensors"
    groups: dict = {}
    for s in ggufs:
        if not any(k in s["rfilename"].lower() for k in SKIP):
            groups.setdefault(SHARD.sub(".gguf", s["rfilename"]), []).append(s)
    if file:
        exact = [s for s in sib if s["rfilename"] == file]
        hit = groups.get(SHARD.sub(".gguf", file)) if file.lower().endswith(".gguf") else None
        hit = hit or next((g for k, g in groups.items() if _quant(k).lower() == file.lower()), None) or exact
        if not hit:
            raise HubError("no_file", f"{info.get('id')} has no file {file}; it lists "
                           + ", ".join(sorted(groups) or [s["rfilename"] for s in sib][:12]))
        return [_row(s) for s in sorted(hit, key=lambda s: s["rfilename"])], kind
    if kind != "gguf":
        return [_row(s) for s in sib if s["rfilename"] not in SKIP_WHOLE], kind
    if not groups:
        raise HubError("no_file", f"{info.get('id')} lists no model file to download")
    by_q = {_quant(k).upper(): k for k in groups}
    key = next((by_q[q] for q in PREFERRED if q in by_q), None) or sorted(groups)[len(groups) // 2]
    return [_row(s) for s in sorted(groups[key], key=lambda s: s["rfilename"])], kind


def prepare(repo: str, file: Optional[str] = None, *, token: Optional[str] = None) -> dict:
    repo = str(repo or "").strip().strip("/")
    if repo.count("/") != 1:
        raise HubError("bad_repo", f"a repo is <org>/<name>, got {repo!r}")
    info = repo_info(repo, token)
    files, kind = pick_files(info, file)
    lic = licence(info, repo)
    total = sum(f["size"] or 0 for f in files)
    return {"repo": repo, "file": file or "", "commit": str(info.get("sha") or "main"), "kind": kind, "files": files,
            "total": total, "licence": lic, "needs_token": bool(lic["gated"]), "token": bool(token),
            "quant": _quant(files[0]["name"]) if files and kind == "gguf" else ""}


def _hasher(f: dict):
    if f.get("sha256"):
        return hashlib.sha256(), "sha256", f["sha256"]
    if f.get("blob_id") and isinstance(f.get("size"), int):
        h = hashlib.sha1()
        h.update(b"blob %d\0" % f["size"])
        return h, "git blob sha1", f["blob_id"]
    return None, "", ""


def _fetch(repo: str, f: dict, root: Path, commit: str, token, on, cancel) -> dict:
    final = root / "snapshots" / commit / f["name"]
    size = f["size"]
    if final.is_file() and (size is None or final.stat().st_size == size):
        on({"status": f"on disk: {f['name']}", "digest": f["name"], "total": size or final.stat().st_size,
            "completed": size or final.stat().st_size})
        return {"name": f["name"], "path": str(final), "size": final.stat().st_size, "resumed_from": 0, "skipped": True}
    part = root / "blobs" / f"{f.get('sha256') or f.get('blob_id') or f['name'].replace('/', '--')}.part"
    part.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.is_file() else 0
    if size is not None and have > size:
        part.unlink()
        have = 0
    h, how, want = _hasher(f)
    if h is not None and have:
        with open(part, "rb") as fh:
            for block in iter(lambda: fh.read(CHUNK), b""):
                h.update(block)
    resumed = have
    if size is None or have < size:
        url = f"{hub_base()}/{repo}/resolve/main/{urllib.parse.quote(f['name'])}"
        hdr = {**_auth(token), **({"Range": f"bytes={have}-"} if have else {})}
        try:
            resp = _open(url, hdr)
        except urllib.error.HTTPError as e:
            if e.code == 416 and size is not None and have >= size:
                resp = None
            elif e.code in (401, 403):
                raise HubError("gated", f"the hub refused {f['name']} ({e.code}): " + (
                    "the token cannot read it -- accept the repo's terms on huggingface.co/" + repo + " first"
                    if token else "the repo is gated: set HF_TOKEN (Setup -> Providers -> Hugging Face)")) from None
            else:
                raise HubError("http", f"the hub answered {e.code} for {f['name']}") from None
        if resp is not None:
            with resp:
                if have and getattr(resp, "status", 200) != 206:
                    have, resumed = 0, 0  # the server sent the whole file: start the part again
                    h, how, want = _hasher(f)
                total = size if size is not None else have + int(resp.headers.get("Content-Length") or 0)
                with open(part, "ab" if have else "wb") as out:
                    on({"status": f"downloading {f['name']}", "digest": f["name"], "total": total, "completed": have})
                    for block in iter(lambda: resp.read(CHUNK), b""):
                        out.write(block)
                        have += len(block)
                        if h is not None:
                            h.update(block)
                        on({"status": f"downloading {f['name']}", "digest": f["name"], "total": total, "completed": have})
                        if cancel is not None and cancel.is_set():
                            return {"name": f["name"], "cancelled": True, "part": str(part), "have": have}
    if size is not None and have != size:
        return {"name": f["name"], "cancelled": True, "part": str(part), "have": have,
                "say": f"{f['name']}: the hub stopped at {have:,} of {size:,} bytes; downloading again resumes"}
    if h is not None and h.hexdigest() != want:
        part.unlink(missing_ok=True)
        raise HubError("checksum", f"{f['name']}: the {how} does not match the hub's ({h.hexdigest()[:12]} != "
                       f"{want[:12]}); the part file was removed, downloading again starts over")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(part, final)
    return {"name": f["name"], "path": str(final), "size": have, "resumed_from": resumed, "checked": how or "size"}


def download(repo: str, file: Optional[str] = None, *, dest_dir, token: Optional[str] = None,
             on_status: Optional[Callable] = None, cancel=None, plan: Optional[dict] = None) -> dict:
    on = on_status or (lambda _obj: None)
    try:
        plan = plan or prepare(repo, file, token=token)
        if plan["needs_token"] and not token:
            return {"ok": False, "error": "gated", "plan": plan, "say": plan["licence"]["line"] + "; set HF_TOKEN first"}
        root = repo_dir(dest_dir, plan["repo"])
        for f in plan["files"]:
            on({"status": "queued", "digest": f["name"], "total": f["size"] or 0, "completed": 0})
        done = []
        for f in plan["files"]:
            got = _fetch(plan["repo"], f, root, plan["commit"], token, on, cancel)
            if got.get("cancelled"):
                say = got.get("say") or (f"stopped: the part file keeps {got['have']:,} bytes of {f['name']}; "
                                         "downloading again resumes from it")
                return {"ok": False, "cancelled": True, "say": say, "files": done, "part": got["part"], "plan": plan}
            done.append(got)
        (root / "refs").mkdir(parents=True, exist_ok=True)
        (root / "refs" / "main").write_text(plan["commit"], encoding="utf-8")
        path = done[0]["path"] if plan["kind"] == "gguf" else str(root / "snapshots" / plan["commit"])
        return {"ok": True, "say": f"{plan['repo']} is on disk in {dest_dir}", "files": done, "path": path,
                "dir": str(dest_dir), "plan": plan}
    except HubError as e:
        return {"ok": False, "error": e.kind, "say": e.message, "plan": plan}
    except OSError as e:
        return {"ok": False, "error": "disk", "say": f"writing into {dest_dir} failed: {e}", "plan": plan}

