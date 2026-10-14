"""tools/capture_flow.py -- the Flow and Media captures for
tools/capture_studio.py (Halo 3.0.4.0 round R6): a Studio over a temp state
dir with a FakeComfy beside it (tests/helpers/flow_studio_rig.py), a
finished social-post run and a run parked at its confirm gate (the R3
fakes), the inventory scanned, and the renders repainted with a drawn
lighthouse so the screenshot shows a picture rather than the fake's 1x1
pixel. `--mode flow` writes docs/media/studio-flow.png, `--mode media`
docs/media/studio-media.png (the Media panels opened at the top); with
`--dom` both runs, the Start view and the section with ComfyUI down are
dumped and their data-testid values counted.
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

FLOW_IDS = ("section-tab", "flow-intake", "flow-graph", "flow-step", "flow-renders", "flow-posts", "flow-metrics",
            "flow-log", "flow-report", "gate-diamond", "gate-card", "gate-answered", "flow-post", "flow-artboard",
            "flow-rail-run", "media-status", "media-models", "media-workflows", "media-render", "flow-start",
            "flow-intake-form", "media-fix")
MEDIA_OPEN = "media-status,media-models,media-workflows,media-render"


def flow_counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in FLOW_IDS}


def _png(w: int, h: int, pixel) -> bytes:
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        for x in range(w):
            rows.extend(pixel(x / w, y / h))
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def lighthouse(u: float, v: float) -> bytes:
    """A lighthouse at dusk, cinematic (the fake Art Director's prompt), in a few gradients."""
    sea = 0.72
    if v < sea:  # sky: deep blue to amber at the horizon, a low sun
        t = v / sea
        r, g, b = 20 + 215 * t ** 2.2, 24 + 120 * t ** 2.6, 60 + 40 * t
        d = math.hypot(u - 0.68, (v - 0.64) * 1.25)
        glow = max(0.0, 1 - d / 0.22)
        r, g, b = r + 60 * glow, g + 50 * glow, b + 20 * glow
    else:  # sea: dark with a sun streak
        t = (v - sea) / (1 - sea)
        streak = max(0.0, 1 - abs(u - 0.68) / (0.03 + 0.12 * t)) * (1 - t) * 0.8
        r, g, b = 14 + 150 * streak, 22 + 90 * streak, 40 + 30 * streak - 10 * t
    tower = abs(u - 0.3) < 0.035 - (v - 0.36) * 0.03 and 0.36 < v < sea + 0.02
    if tower:
        r, g, b = (230, 225, 215) if int(v * 40) % 4 < 2 else (150, 40, 50)
    if 0.31 < v < 0.36 and abs(u - 0.3) < 0.03:  # the lamp room
        r, g, b = 255, 236, 170
    beam = 0.3 < u < 0.95 and abs((v - 0.335) - (u - 0.3) * -0.12) < 0.012 + (u - 0.3) * 0.05
    if beam and not tower:
        r, g, b = r + 50, g + 45, b + 25
    rock = v > sea - 0.02 and abs(u - 0.3) < 0.12 - (v - sea) * 0.2
    if rock:
        r, g, b = 10, 12, 18
    return bytes(int(max(0, min(255, c))) for c in (r, g, b))


def paint_renders(state: Path) -> int:
    """Repaint every render.png under the state's design projects; returns how many."""
    png = _png(288, 360, lighthouse)
    n = 0
    for p in Path(state).glob("design/**/render.png"):
        p.write_bytes(png)
        n += 1
    return n


def capture(mode: str, out: str, dom: bool, chrome, url_for) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers.flow_studio_rig import FlowStudio
    with FlowStudio() as s:
        done = s.finished_run()
        wait, _thread, _box = s.waiting_run()
        s.post("media/scan")
        paint_renders(s.state)
        # two runs made in the same second sort by their random suffix: name the run to open
        url = url_for(s.srv).replace("/#t=", "/?mode=flow&feed=off&run={run}#t=")
        base = url.format(run=done.name).replace("#t=", f"&open={MEDIA_OPEN}#t=") if mode == "media" else url.format(run=wait.name)
        if dom:
            a = chrome(["--dump-dom", "--window-size=1500,900", url.format(run=wait.name)])
            b = chrome(["--dump-dom", "--window-size=1500,900", url.format(run=done.name)])
            c = chrome(["--dump-dom", "--window-size=1500,900", url.format(run=done.name).replace("#t=", "&view=start#t=")])
            from halo_harness.studio import media_api
            # ComfyUI does not answer (an address that is not ComfyUI: Studio's own port): one status card, not four panels
            media_api.URL = f"http://127.0.0.1:{s.srv.server_address[1]}/no-comfyui-here"
            media_api._status.clear()
            d = chrome(["--dump-dom", "--window-size=1500,900", url.format(run=done.name).replace("#t=", "&open=media-status#t=")])
            if a is None or b is None or c is None or d is None:
                print("no Chrome found")
                return 2
            print(json.dumps({"waiting": flow_counts(a.stdout), "finished": flow_counts(b.stdout), "start": flow_counts(c.stdout),
                              "down": flow_counts(d.stdout)}))
            return 0
        path = Path(out).resolve()
        r = chrome([f"--screenshot={path}", "--window-size=1500,900", "--force-device-scale-factor=2", base])
        if r is None:
            print("no Chrome found: nothing rendered")
            return 2
        ok = path.is_file() and path.stat().st_size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {path} ({path.stat().st_size if path.is_file() else 0} bytes)")
        return 0 if ok else 1
