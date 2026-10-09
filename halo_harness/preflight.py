"""halo_harness.preflight -- Halo 2.0.7 cyber Pillar 2: the
verify-everything preflight gate.

`halo preflight` is the exit-code-gated check a long autonomous run is
worth starting under: local tools verified BY EFFECT (not "didn't error"
-- the file really contains the bytes, the grep really matched), one
measured canary per provider lane (connectivity + a real completion, a
tool call the lane must actually emit and the tool must actually run, an
image the lane must actually accept when its profile claims vision, and
a truncation check comparing the usage echo against what was sent), and
every result recorded into the canary census (`<state_dir>/canary-
census.json`) so role binding (the later `doctor --roles` round) can
prefer lanes that MEASURED healthy over datasheets.

Nothing here probes with anything exotic: every canary is the smallest
real request that could ever appear in a working session. A lane that
cannot answer "pong" cannot run your work; a lane that cannot emit one
tool call cannot drive your tools; a lane that 400s on one tiny PNG
cannot be the eyes lane its profile says it is.
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path
from typing import Optional

from halo_harness.config.paths import bridge_home
from halo_harness.tools.base import Tool, ToolResult


# ---- the canary census (measured lane health, on disk) ------------------------

def _census_path(state_dir) -> Optional[Path]:
    if state_dir is None:
        return None
    return Path(state_dir) / "canary-census.json"


def load_canary_census(state_dir) -> dict:
    path = _census_path(state_dir)
    if path is None or not path.exists():
        return {"lanes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"lanes": {}}
    if not isinstance(data, dict):
        return {"lanes": {}}
    data.setdefault("lanes", {})
    return data


def record_canary_result(state_dir, raw_ref: str, result: dict) -> None:
    """One lane's canary outcome into the census (best-effort, same
    contract as the filter census: telemetry, never a failure reason)."""
    path = _census_path(state_dir)
    if path is None or not raw_ref:
        return
    entry = dict(result)
    entry["recorded"] = time.time()
    try:
        data = load_canary_census(state_dir)
        data["lanes"][raw_ref] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except Exception:
        pass


# ---- local tools, verified by effect -------------------------------------------

def run_local_checks(scratch: Path) -> list:
    """Each check runs a REAL tool path and verifies the EFFECT: the bytes
    on disk, the matched line, the echoed marker. A tool that "succeeds"
    without producing the effect fails the gate."""
    from halo_harness.tools.bash import BashTool
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.edit import EditTool
    from halo_harness.tools.glob_tool import GlobTool
    from halo_harness.tools.grep_tool import GrepTool
    from halo_harness.tools.read import ReadTool
    from halo_harness.tools.write import WriteTool

    checks = []

    def _record(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    marker = f"halo-preflight-{int(time.time() * 1000) % 1000000}"
    ctx = ToolContext(cwd=scratch)

    try:
        result = BashTool().run({"command": f"echo {marker}"}, ctx)
        _record("Bash", marker in result.content and not result.is_error, result.content.strip()[:80])
    except Exception as e:
        _record("Bash", False, f"{type(e).__name__}: {e}")

    target = scratch / "preflight-probe.txt"
    try:
        WriteTool().run({"file_path": str(target), "content": f"{marker} line one\n"}, ctx)
        read_back = ReadTool().run({"file_path": str(target)}, ctx)
        ok = f"{marker} line one" in read_back.content
        EditTool().run({"file_path": str(target), "old_string": "line one",
                        "new_string": "line two"}, ctx)
        edited = ReadTool().run({"file_path": str(target)}, ctx)
        ok = ok and f"{marker} line two" in edited.content and "line one" not in edited.content
        _record("Write+Read+Edit", ok, target.name)
    except Exception as e:
        _record("Write+Read+Edit", False, f"{type(e).__name__}: {e}")

    try:
        globbed = GlobTool().run({"pattern": "preflight-probe.txt", "path": str(scratch)}, ctx)
        grepped = GrepTool().run({"pattern": marker, "path": str(scratch)}, ctx)
        ok = (target.name in globbed.content) and (target.name in grepped.content)
        _record("Glob+Grep", ok, target.name)
    except Exception as e:
        _record("Glob+Grep", False, f"{type(e).__name__}: {e}")

    return checks


# ---- the lane canary -----------------------------------------------------------

def _tiny_png() -> bytes:
    """A valid 8x8 solid-red PNG, hand-built (no image deps) -- the
    smallest real image a vision lane must accept."""
    width = height = 8
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


class _CanaryProbeTool(Tool):
    """The tool-call canary instrument: the model must CALL it with a
    known echo value; the recorded invocation is the measured proof."""

    name: str = "PreflightProbe"
    description: str = ("Echo back exactly the value given in `echo`. "
                        "Use this tool when asked to run a preflight probe.")
    input_schema: dict = {"type": "object",
                          "properties": {"echo": {"type": "string", "description": "the value to echo back"}},
                          "required": ["echo"]}
    is_read_only: bool = True
    is_destructive: bool = False
    result_cap: Optional[int] = 1000

    def __init__(self):
        self.invocations = []
        super().__init__()

    def run(self, input: dict, ctx) -> ToolResult:
        echo = input.get("echo", "") if isinstance(input, dict) else ""
        self.invocations.append(echo)
        return ToolResult(f"preflight-probe-echo: {echo}")

    def summary(self, input: dict) -> str:
        return f"PreflightProbe({(input or {}).get('echo', '')!r})"


def run_lane_canary(raw_ref: str, *, state_dir, settings=None, cwd: Optional[Path] = None,
                    timeout_s: float = 90.0, include_vision: bool = True,
                    openrouter_base_url: Optional[str] = None) -> dict:
    """One measured canary against one lane. Returns
    `{"ref", "ok", "checks": {...}, "error"}` -- never raises."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref, resolve_model_profile
    from halo_harness.permissions import PermissionEngine
    from halo_harness.tools.registry import ToolRegistry

    out = {"ref": raw_ref, "ok": False,
           "checks": {"text": None, "tools": None, "vision": None, "truncation": None},
           "error": None}
    scratch = Path(tempfile.mkdtemp(prefix="halo-preflight-lane-"))
    try:
        ref = parse_model_ref(raw_ref)
        profile = resolve_model_profile(ref, state_dir, {})
        creds = _resolve_creds(ref, settings)
        if creds is None:
            out["error"] = f"no usable credentials for {raw_ref}"
            return out
        if openrouter_base_url is None and ref.provider == "openrouter":
            # The same HALO_OPENROUTER_BASE_URL/BRIDGE_OPENROUTER_BASE_URL
            # self-hosted-proxy override a real session honors (headless.
            # py's build_session) -- a preflight under that setup must
            # canary the ACTUAL lane the sessions use.
            from halo_harness.config.paths import env_compat
            openrouter_base_url = env_compat("OPENROUTER_BASE_URL")
        probe = _CanaryProbeTool()
        session_ctx = SessionContext(cwd=scratch, model_label=raw_ref, bare=True,
                                     tool_registry=ToolRegistry([probe]))
        session = Session(
            cwd=scratch, model_ref=ref, model_profile=profile, creds=creds,
            state_dir=state_dir, model_label=raw_ref, session_context=session_ctx,
            permission_engine=PermissionEngine(mode="auto", cwd=scratch),
            agents={}, routes={}, max_turns=4,
            openrouter_base_url=openrouter_base_url,
        )
    except Exception as e:
        out["error"] = f"lane unresolvable: {type(e).__name__}: {e}"
        return out

    def _drive(turn_fn):
        """Run one session turn with a wall-clock cap the turn machinery
        itself has no opinion about -- on timeout, abort and report."""
        box = {}

        def _worker():
            try:
                box["events"] = list(turn_fn())
            except Exception as e:
                box["error"] = f"{type(e).__name__}: {e}"

        t = threading.Thread(target=_worker, daemon=True, name="halo-preflight")
        t.start()
        t.join(timeout_s)
        if t.is_alive():
            session.abort.set()
            t.join(min(5.0, timeout_s))
            return None, "lane timed out"
        if "error" in box:
            return None, box["error"]
        return box.get("events", []), None

    # -- 1. tool-call canary FIRST (measured: the probe must actually run).
    #    Order matters for scripted-test upstreams: a scenario's steps key
    #    on tool-result count in the request, so the tool turn (step 0 ->
    #    tool call -> step 1) must precede the text canary for both to be
    #    servable; for a real lane the order is irrelevant.
    events, err = _drive(lambda: session.turn(
        "Call the PreflightProbe tool with echo=\"canary42\" and then tell me its exact output."))
    if err is not None:
        out["error"] = f"tool canary: {err}"
        out["checks"]["tools"] = False
        return out
    tool_uses = [n for n in session.log.nodes() if n.get("type") == "assistant"
                 for b in (n.get("content") or []) if isinstance(b, dict) and b.get("type") == "tool_use"]
    out["checks"]["tools"] = ("canary42" in probe.invocations)
    if not out["checks"]["tools"]:
        out["error"] = (f"lane emitted {len(tool_uses)} tool call(s) but the probe never ran "
                        f"(tool-call capability missing or malformed)")

    # -- 2. text + truncation canary (one request, padded prompt) -------------
    pad_lines = 240
    pad = "\n".join(f"canary filler line {i:04d} of {pad_lines} -- ignore this line" for i in range(pad_lines))
    events, err = _drive(lambda: session.turn(f"{pad}\n\nReply with exactly one word: pong"))
    if err is not None:
        out["error"] = err
        return out
    final_text = "".join(e.data.get("text", "") for e in events if e.kind == "text_delta")
    errors = [e for e in events if e.kind == "error"]
    if errors:
        out["error"] = errors[0].data.get("message", "lane errored")
        out["checks"]["text"] = False
        return out
    out["checks"]["text"] = bool(final_text.strip())
    if not out["checks"]["text"]:
        out["error"] = "lane returned no text for the canary prompt"
        return out

    # truncation: the usage echo must account for at least half of what
    # we estimate was sent (cache reads/writes count toward what the
    # provider saw; only a REAL silent truncation lands far below).
    usage_nodes = [n for n in session.log.nodes() if n.get("type") == "usage"]
    if usage_nodes:
        u = usage_nodes[-1].get("usage") or {}
        seen = sum(int(u.get(k) or 0) for k in
                   ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        est = max(1, (len(pad) + 64) // 4)
        out["checks"]["truncation"] = seen >= est * 0.5
    else:
        out["checks"]["truncation"] = None  # lane echoes no usage -- unknowable

    # -- 3. vision canary (only when the profile claims it) -------------------
    if include_vision and getattr(profile, "vision", False):
        png = scratch / "canary.png"
        png.write_bytes(_tiny_png())
        events, err = _drive(lambda: session.turn(
            "Describe the color of this image in one word.",
            images=[{"type": "image", "path": str(png)}]))
        if err is not None:
            out["checks"]["vision"] = False
            out["error"] = f"vision canary: {err}"
        else:
            v_errors = [e for e in events if e.kind == "error"]
            v_text = "".join(e.data.get("text", "") for e in events if e.kind == "text_delta")
            out["checks"]["vision"] = bool(v_text.strip()) and not v_errors
            if not out["checks"]["vision"] and out["error"] is None:
                out["error"] = "lane claims vision but rejected/failed the image canary"
    else:
        out["checks"]["vision"] = None  # not claimed -- not tested

    out["ok"] = bool(out["checks"]["text"]) and out["checks"]["tools"] is True \
        and out["checks"]["vision"] in (True, None) and out["checks"]["truncation"] in (True, None)
    return out


# ---- the CLI --------------------------------------------------------------------

def _default_lane(state_dir) -> Optional[str]:
    """The session's current default model, if one can be identified.
    vibes/review.md finding 81: this used to read config.json's
    model/last_model ONLY -- a session whose model comes from HALO_MODEL
    or routes.json resolved NO lane, preflight checked 0 lanes, and still
    printed PASS (a vacuous pass is worse than none). All three sources
    are consulted now."""
    from halo_harness.config.paths import env_compat
    env_lane = env_compat("MODEL")
    if env_lane:
        return str(env_lane)
    try:
        cfg = json.loads((Path(state_dir) / "config.json").read_text(encoding="utf-8"))
        lane = cfg.get("model") or cfg.get("last_model")
        if lane:
            return str(lane)
    except Exception:
        pass
    try:
        routes = json.loads((Path(state_dir) / "routes.json").read_text(encoding="utf-8"))
        lane = routes.get("model")
        if lane:
            return str(lane)
    except Exception:
        pass
    return None


def cmd_preflight(argv: list) -> int:
    """`halo preflight [--lanes a,b] [--json] [--skip-local] [--no-vision]
    [--timeout S]` -- exit 0 iff every check passed."""
    lanes = None
    as_json = False
    skip_local = False
    include_vision = True
    timeout_s = 90.0
    rest = list(argv)
    while rest:
        a = rest.pop(0)
        if a == "--lanes" and rest:
            lanes = [x.strip() for x in rest.pop(0).split(",") if x.strip()]
        elif a == "--json":
            as_json = True
        elif a == "--skip-local":
            skip_local = True
        elif a == "--no-vision":
            include_vision = False
        elif a == "--timeout" and rest:
            try:
                timeout_s = float(rest.pop(0))
            except ValueError:
                pass
        else:
            print(f"halo preflight: unknown argument {a!r}", file=sys.stderr)
            return 2

    state_dir = bridge_home()
    if lanes is None:
        lane = _default_lane(state_dir)
        lanes = [lane] if lane else []
    if skip_local and not lanes:
        # Nothing to check at all (--skip-local with no lanes and no pinned
        # default model) -- a usage error, not a vacuous PASS.
        print("halo preflight: no lanes to check (pass --lanes or pin a default model)", file=sys.stderr)
        return 2
    if not skip_local and not lanes:
        # finding 81's other half: local checks alone are NOT a preflight
        # PASS when the operator never asked for local-only -- no lane
        # could be identified (no --lanes, no HALO_MODEL, no routes.json
        # default, no pinned model), so fail loudly instead of printing
        # "PASS (0 lane(s) checked)".
        print("halo preflight: no model lane identified -- pass --lanes, set HALO_MODEL, "
              "or pin a default model (local-only preflight is --skip-local)", file=sys.stderr)
        return 2

    report = {"local": None, "lanes": {}, "ok": True}
    if not skip_local:
        scratch = Path(tempfile.mkdtemp(prefix="halo-preflight-"))
        report["local"] = run_local_checks(scratch)
        report["ok"] = all(c["ok"] for c in report["local"]) and report["ok"]

    for raw in lanes:
        result = run_lane_canary(raw, state_dir=state_dir, timeout_s=timeout_s,
                                 include_vision=include_vision)
        record_canary_result(state_dir, raw, result)
        report["lanes"][raw] = result
        if not result["ok"]:
            report["ok"] = False

    if as_json:
        print(json.dumps(report, indent=1))
    else:
        if report["local"] is not None:
            for c in report["local"]:
                mark = "ok " if c["ok"] else "FAIL"
                print(f"  [{mark}] local {c['name']}: {c['detail']}")
        for raw, r in report["lanes"].items():
            mark = "ok " if r["ok"] else "FAIL"
            checks = ", ".join(f"{k}={('PASS' if v else ('n/a' if v is None else 'FAIL'))}"
                               for k, v in r["checks"].items())
            print(f"  [{mark}] lane {raw}: {checks}")
            if r.get("error"):
                print(f"         {r['error']}")
        print(f"preflight: {'PASS' if report['ok'] else 'FAIL'} "
              f"({len(report['lanes'])} lane(s) checked; canary census updated)")
    return 0 if report["ok"] else 1
