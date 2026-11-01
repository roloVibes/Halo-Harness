"""halo_harness.local_pool.versions -- the llama.cpp build on the controller and on every rpc-server (Halo 3.3.8.0 R3;
docs/POOL.md "The preflight").

Workers hold no GGUF: the controller's llama-server ships the tensors to each worker's rpc-server, so the mismatch
that matters is llama.cpp's own -- both ends must speak one RPC protocol, which changes between builds. llama.cpp's
programs print their build on `--version` ("version: 7210 (a1b2c3d)"); rpc-server prints its RPC protocol when it
starts ("Starting RPC server v3.0.0"). Both lines are read as text; nothing here loads a model.

    parse(text) -> {build, commit, rpc_proto, line}            build: an int (b7210), None when the text has none
    read(prefix) -> {build, commit, rpc_proto, line, source, ok}
        `<prefix> --version`, cached per binary path + mtime (a new build on disk is read again); SEAMS["run"]
        (fn(argv) -> (exit code, text)) is the tests' `--version` answer, so no binary runs in a test
    word(v) -> "b7210 (a1b2c3d)" | "rpc v3.0.0" | "not known"
    controller(state_dir=None) -> the version of the llama-server `halo local serve` would run, + `binary`
    compare(ctl, workers) -> (blocks, notes)     workers: [{name, version}]; a build or an RPC protocol that differs
        blocks with both versions printed; a version not known is a note (llama-server checks the protocol itself
        when it connects, and refuses a worker that differs)
    min_build(model, ctl, workers) -> (blocks, notes)   the model's `min_build` (Qwen3-Next: b7186+) on every node
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

SEAMS: dict = {}
_CACHE: dict = {}
BUILD = (re.compile(r"version:\s*(\d{2,7})\s*\(([0-9A-Za-z]{5,40})\)"), re.compile(r"\bbuild[:=]?\s*b?(\d{2,7})\b"),
         re.compile(r"\bb(\d{3,7})\b"))
PROTO = re.compile(r"RPC server v(\d+\.\d+\.\d+)|RPC_PROTO\w*\s*[:=]?\s*v?(\d+\.\d+\.\d+)", re.IGNORECASE)


def parse(text: str) -> dict:
    t = str(text or "")
    out = {"build": None, "commit": None, "rpc_proto": None, "line": ""}
    for i, rx in enumerate(BUILD):
        m = rx.search(t)
        if m:
            out["build"], out["commit"] = int(m.group(1)), (m.group(2) if i == 0 else None)
            out["line"] = next((ln.strip() for ln in t.splitlines() if m.group(0) in ln), m.group(0))
            break
    m = PROTO.search(t)
    if m:
        out["rpc_proto"] = m.group(1) or m.group(2)
        out["line"] = out["line"] or m.group(0)
    return out


def _key(prefix: list) -> tuple:
    marks = []
    for p in prefix:
        try:
            st = Path(p).stat()
            marks.append((str(p), st.st_mtime_ns, st.st_size))
        except (OSError, ValueError):
            marks.append((str(p), None, None))
    return tuple(marks)


def _run(argv: list) -> "tuple[int, str]":
    if "run" in SEAMS:
        return SEAMS["run"](argv)
    from halo_harness.config.paths import background_net_disabled
    if background_net_disabled():
        return 127, "not run under the test flag (BRIDGE_TEST_NO_BACKGROUND_NET): no llama.cpp binary runs in a test"
    try:
        import os
        from halo_harness.providers.config import tool_child_env
        r = subprocess.run(argv, capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL,
                           env=tool_child_env(dict(os.environ)), errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, f"{type(e).__name__}: {e}"
    return r.returncode, (r.stdout or "") + "\n" + (r.stderr or "")


def read(prefix: Optional[list]) -> dict:
    if not prefix:
        return {"build": None, "commit": None, "rpc_proto": None, "line": "", "source": "no binary", "ok": False}
    key = _key(list(prefix))
    if key in _CACHE:
        return dict(_CACHE[key])
    code, text = _run(list(prefix) + ["--version"])
    got = parse(text)
    got.update(source=f"{Path(str(prefix[-1])).name} --version", ok=got["build"] is not None or got["rpc_proto"] is not None)
    if not got["ok"]:
        got["line"] = (text.strip().splitlines() or [f"exit {code}"])[-1][:200]
    _CACHE[key] = dict(got)
    return got


def forget() -> None:
    _CACHE.clear()


def word(v: Optional[dict]) -> str:
    v = v or {}
    bits = []
    if v.get("build"):
        bits.append(f"b{v['build']}" + (f" ({v['commit']})" if v.get("commit") else ""))
    if v.get("rpc_proto"):
        bits.append(f"rpc v{v['rpc_proto']}")
    return ", ".join(bits) or "not known"


def controller(state_dir=None) -> dict:
    from halo_harness.providers.local_server_cmd import binary
    prefix, why = binary("llama-server", state_dir=state_dir)
    got = read(prefix) if prefix else {"build": None, "commit": None, "rpc_proto": None, "line": why, "ok": False,
                                       "source": "no llama-server"}
    return {**got, "binary": why, "prefix": prefix}


def compare(ctl: dict, workers: list) -> "tuple[list, list]":
    blocks, notes = [], []
    for w in workers:
        v = w.get("version") or {}
        name = w.get("name") or "a worker"
        if ctl.get("build") and v.get("build") and ctl["build"] != v["build"]:
            blocks.append(f"version mismatch: llama-server here is {word(ctl)}, rpc-server on {name} is {word(v)} -- "
                          "the controller and every rpc-server run one llama.cpp build (the RPC protocol changes "
                          "between builds)")
        elif ctl.get("rpc_proto") and v.get("rpc_proto") and ctl["rpc_proto"] != v["rpc_proto"]:
            blocks.append(f"RPC protocol mismatch: llama-server here speaks rpc v{ctl['rpc_proto']}, rpc-server on "
                          f"{name} speaks rpc v{v['rpc_proto']}")
        elif not v.get("build") and not v.get("rpc_proto"):
            notes.append(f"rpc-server on {name}: its version is not known ({v.get('line') or 'not read'}); llama-server "
                         "checks the RPC protocol when it connects and refuses a worker that differs")
        elif not ctl.get("build") and not ctl.get("rpc_proto"):
            notes.append(f"llama-server here: its version is not known ({ctl.get('line') or 'not read'}), so "
                         f"{name}'s {word(v)} is not compared")
    return blocks, notes


def min_build(model: dict, ctl: dict, workers: list) -> "tuple[list, list]":
    need = model.get("min_build")
    if not need:
        return [], []
    blocks, notes = [], []
    for name, v in [("llama-server here", ctl)] + [(f"rpc-server on {w.get('name')}", w.get("version") or {}) for w in workers]:
        if v.get("build") and int(v["build"]) < int(need):
            blocks.append(f"{model.get('display') or model.get('name')} needs llama.cpp b{need}+: {name} is b{v['build']}")
        elif not v.get("build"):
            notes.append(f"{model.get('display') or model.get('name')} needs llama.cpp b{need}+: the build of {name} is "
                         "not known")
    return blocks, notes
