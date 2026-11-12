"""halo_harness.live.replay_clip -- "Export a clip" (Halo 3.4.1.0 R1 "Time"): a scrubbed range of a saved replay
filmed on Agents -> Live and written as ONE animated file, the way the capture tooling assembles its front-page
animations (tools/capture_session_anim.py: Chrome frames, Pillow writes the file).

    plan(payload, frm, to, speed) -> {from, to, speed, frames, seconds, fps, times, width, note}   nothing written
    encoder()                     -> {format, pillow, needs}: what would write the file, asked without Pillow too
    assemble(pngs, path, fps)     -> bytes written (WebP when Pillow has it, else GIF; WIDTH px wide)
    clip(state_dir, rid, ...)     -> {ok, path, bytes, frames, seconds, ...}  films it through a Studio and writes
                                     <state>/replays/clips/<id>-<from>-<to>.webp|.gif

The clip is WIDTH px wide, FPS frames a second, at most MAX_SECONDS long: a range that would run longer at the asked
speed is played faster to fit (`note` says so). Needs Chrome (HALO_CHROME, else the usual install) and Pillow
(`uv tool install "halo-harness[images]"`); without either it says which and writes nothing. 3.4.1.0 R6: saying what a
clip WILL write (the plan, `--dry-run`, the dialog) needs neither: only the encode needs Pillow, and `encoder()` says so
in one line, with the install command, before anything is written.
"""

from __future__ import annotations

import io
import math
import secrets
import threading
from pathlib import Path
from typing import Callable, Optional

WIDTH = 1200
FPS = 5
MAX_SECONDS = 30
MAX_FRAMES = FPS * MAX_SECONDS + 1
MAX_BYTES = 16_000_000
SPEEDS = (1, 4, 16, 64, 256, 1024)
VIEW = (1500, 900)


class ClipError(RuntimeError):
    """What is missing or wrong, in one line."""


def plan(payload: dict, frm: Optional[float] = None, to: Optional[float] = None, speed: Optional[float] = None) -> dict:
    """The frames of the range [frm, to] (seconds since the replay's start) at `speed`."""
    t0, t1 = payload.get("started"), payload.get("ended")
    if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)) or t1 <= t0:
        raise ClipError("this replay has no time span to film")
    span = float(t1 - t0)
    a = max(0.0, min(span, float(frm) if frm is not None else 0.0))
    b = max(0.0, min(span, float(to) if to is not None else span))
    if b <= a:
        raise ClipError(f"the range is empty: from {a:.0f} s to {b:.0f} s (the replay is {span:.0f} s long)")
    note = ""
    want = float(speed) if speed else next((s for s in SPEEDS if (b - a) / s <= MAX_SECONDS), SPEEDS[-1])
    fit = (b - a) / MAX_SECONDS
    if want < fit:
        note = f"played at {fit:.0f}x instead of {want:g}x to stay within {MAX_SECONDS} s"
        want = math.ceil(fit)
    seconds = (b - a) / want
    frames = max(2, min(MAX_FRAMES, int(math.ceil(seconds * FPS)) + 1))
    times = [round(a + (b - a) * i / (frames - 1), 3) for i in range(frames)]
    return {"from": a, "to": b, "speed": want, "frames": frames, "seconds": round(seconds, 2), "fps": FPS,
            "width": WIDTH, "times": times, "note": note, "max_seconds": MAX_SECONDS}


NEEDS_PILLOW = ('encoding a clip needs Pillow, which is not installed here: uv tool install "halo-harness[images]" '
                '(or pip install Pillow)')


def _pil():
    try:
        from PIL import Image, features
    except ImportError:
        raise ClipError(NEEDS_PILLOW) from None
    return Image, features


def encoder() -> dict:
    """What would write the clip, asked without encoding anything: {format, pillow, needs}. Without Pillow the plan
    still says everything else and `needs` is the one line that says what to install; the file would be WebP (Pillow's
    wheels write animated WebP), GIF when the Pillow installed has no WebP."""
    try:
        return {"format": fmt(), "pillow": True, "needs": ""}
    except ClipError as e:
        return {"format": "webp", "pillow": False, "needs": str(e)}


def fmt() -> str:
    _Image, features = _pil()
    try:
        return "webp" if features.check("webp_anim") else "gif"
    except Exception:
        return "gif"


def assemble(pngs: list, path: Path, fps: int = FPS) -> int:
    Image, _f = _pil()
    frames = []
    for raw in pngs:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.width != WIDTH:
            im = im.resize((WIDTH, max(1, round(im.height * WIDTH / im.width))))
        frames.append(im)
    if not frames:
        raise ClipError("no frames to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    ms = int(1000 / fps)
    if path.suffix == ".webp":
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, quality=70, method=4)
    else:
        q = [f.quantize(colors=128) for f in frames]
        q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True)
    size = path.stat().st_size
    if size > MAX_BYTES:
        path.unlink(missing_ok=True)
        raise ClipError(f"the clip came out at {size} bytes, over {MAX_BYTES}: film a shorter range")
    return size


SCRUB = "document.querySelector('[data-testid=\"replay-scrub\"]')"
BAR = "document.querySelector('[data-testid=\"replay-bar\"]')"
MAP = "document.querySelector('[data-testid=\"roles-live-map\"]')"


def film(base: str, token: str, rid: str, times: list, exe: str) -> list:
    """A PNG of Live's canvas at each time, through one headless Chrome on the Studio at `base`."""
    from halo_harness.live.clip_chrome import Chrome
    c = Chrome(exe, *VIEW)
    try:
        c.call("Page.navigate", url=f"{base}/?mode=agents&view=live&replay={rid}&level=mid#t={token}")
        try:
            c.wait(f"!!{BAR} && {BAR}.dataset.replay === '{rid}' && !!{SCRUB}", 40)
        except TimeoutError:
            seen = c.js("(document.body && document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 160)")
            raise ClipError(f"Studio did not open replay {rid} on Live within 40 s (the page said: {seen!r})") from None
        out = []
        for t in times:
            v = int(round(t * 10))
            c.js(f"(() => {{ const r = {SCRUB}; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')"
                 f".set.call(r, '{v}'); r.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()")
            c.wait(f"{BAR}.dataset.t10 === '{v}' && new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(() => ok(1))))", 20)
            x, y, w, h = c.js(f"(() => {{ const r = {MAP}.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }})()")
            out.append(c.png(x, y, w, h, WIDTH / max(1.0, w)))
        return out
    finally:
        c.close()


def _studio(state_dir, cwd) -> "tuple[str, str, Callable[[], None]]":
    """A Studio to film in: this process's own, on a free loopback port, stopped after."""
    from halo_harness.studio.server import Handler, _Server
    token = secrets.token_urlsafe(24)
    server = _Server(("127.0.0.1", 0), Handler, token=token, cwd=Path(cwd), state_dir=Path(state_dir), slow_ms=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def stop() -> None:
        server.shutdown()
        server.server_close()
    return f"http://127.0.0.1:{server.server_address[1]}", token, stop


def clip(state_dir, rid: str, frm=None, to=None, speed=None, *, cwd=".", studio: "tuple[str, str] | None" = None,
         frames: Optional[Callable[[list], list]] = None) -> dict:
    """Film replay `rid` (saved under <state>/replays/) and write the clip. `studio` = (base URL, token) of a running
    Studio (its own route passes itself); `frames` stands in for the filming (the tests)."""
    from halo_harness.live import replay_file
    path = replay_file.path_for(state_dir, rid)
    if path is None:
        raise ClipError(f"no saved replay {rid!r} under {replay_file.replays_dir(state_dir)}")
    p = plan(replay_file.load(path), frm, to, speed)
    kind = fmt()
    out = replay_file.replays_dir(state_dir) / "clips" / f"{rid}-{int(p['from'])}-{int(p['to'])}.{kind}"
    if frames is not None:
        pngs = frames(p["times"])
    else:
        exe = __import__("halo_harness.live.clip_chrome", fromlist=["find_chrome"]).find_chrome()
        if not exe:
            raise ClipError("a clip is filmed in Chrome and none was found: install Chrome or set HALO_CHROME")
        stop = None
        if studio is None:
            base, token, stop = _studio(state_dir, cwd)
        else:
            base, token = studio
        try:
            pngs = film(base, token, rid, p["times"], exe)
        finally:
            if stop:
                stop()
    size = assemble(pngs, out, p["fps"])
    return {"ok": True, "path": str(out), "name": out.name, "bytes": size, "format": kind, **{k: p[k] for k in
            ("from", "to", "speed", "frames", "seconds", "fps", "width", "note", "max_seconds")}}
