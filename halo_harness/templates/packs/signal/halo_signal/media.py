"""halo_signal.media -- files both ways (3.3.13.0 R3).

In: a picture goes to the model as the turn's image (the control socket's `submit` carries it, as Studio's paste
does: one image per message, png / jpeg / gif / webp up to 5 MB); a PDF stays in the data folder's inbox/ and the
prompt names its path for the session to read; a voice note is transcribed by the local speech server that runs here
(`halo local serve --stt`, docs/VOICE.md) and sent as the prompt with "(voice note)" in front -- with none running,
one line says how to turn transcription on. Out: `/file <path>` sends a file of the attached session's folder;
`/shot` sends a capture of the Halo Studio window when Studio is open on this computer. Files in inbox/ older than a
day are deleted when the service starts.

    inbound(b, rt, text, files) -> (prompt text, image | None, line)
    send_file(b, rt, arg) -> outcome
    shot(b, rt) -> outcome
    sweep(folder, max_age_s=86400)
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

from halo_harness.ext import remote as R

IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")
MAX_IMAGE = 5 * 1024 * 1024
MAX_OUT = 50 * 1024 * 1024


def _drop(path: str) -> None:
    try:
        Path(path).unlink()
    except OSError:
        pass


def inbound(b, rt, text: str, files: list) -> "tuple[str, object, str]":
    parts, image, lines = [], None, []
    for f in files:
        ctype, path = f.get("content_type", ""), f.get("path", "")
        if f.get("voice"):
            heard, why = b.transcribe(path)
            _drop(path)
            if heard:
                parts.append(f"(voice note) {heard}")
            else:
                lines.append(f"The voice note was not read: {why}")
        elif ctype in IMAGE_TYPES and image is None:
            try:
                data = Path(path).read_bytes()
            except OSError:
                data = b""
            _drop(path)
            if 0 < len(data) <= MAX_IMAGE:
                image = {"media_type": ctype, "data_b64": base64.b64encode(data).decode("ascii")}
            else:
                lines.append("The picture was not sent: it is over 5 MB.")
        elif ctype.startswith("image/"):
            _drop(path)
            lines.append("One picture per message reaches the session; send the others one by one.")
        else:
            parts.append(f"(The phone sent a file: {path} -- {f.get('filename')}, {ctype}. Read it from there.)")
    prompt = "\n".join(([text] if text else []) + parts).strip()
    return prompt, image, " ".join(lines)


def send_file(b, rt, arg: str) -> str:
    if rt.entry is None:
        b.say(rt.aci, "No session is attached: /file sends a file of the attached session's folder.")
        return "no_session"
    if not arg:
        b.say(rt.aci, "Usage: /file <path in the session's folder>")
        return "usage"
    base = Path(str(rt.entry.get("cwd") or ".")).resolve()
    target = (base / arg).resolve() if not Path(arg).is_absolute() else Path(arg).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        b.say(rt.aci, f"{arg} is outside the session's folder ({base.name}); /file sends files from inside it.")
        return "outside"
    if not target.is_file():
        b.say(rt.aci, f"No file {arg} in the session's folder.")
        return "missing"
    if target.stat().st_size > MAX_OUT:
        b.say(rt.aci, f"{target.name} is over {MAX_OUT // (1024 * 1024)} MB; Signal would not carry it.")
        return "too_big"
    b.say(rt.aci, target.name, attachment_path=str(target))
    return "ok"


def shot(b, rt) -> str:
    path, why = b.capture(rt.entry.get("session_id") if rt.entry else "")
    if not path:
        b.say(rt.aci, f"No capture: {why}")
        return "none"
    b.say(rt.aci, "Studio, now:", attachment_path=path)
    return "ok"


def sweep(folder, max_age_s: float = 86400.0) -> int:
    n = 0
    folder = Path(folder)
    for p in folder.glob("*") if folder.is_dir() else []:
        try:
            if p.is_file() and time.time() - p.stat().st_mtime > max_age_s:
                p.unlink()
                n += 1
        except OSError:
            continue
    return n


def default_transcribe(path: str):
    return R.transcribe(path)


def default_capture(session_id: str):
    return R.capture_studio(session_id)
