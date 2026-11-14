"""halo_harness.ext.remote -- the transport seam (extension API 1.2, Halo 3.3.13.0 R3; docs/EXTENSION_API.md
"Transports"). What a pack that carries Halo somewhere else -- a phone, a chat -- uses: the live sessions and their
control sockets, a session started for it, the cards' text, the notes the core hands every transport, a voice note's
transcript, a QR drawing, Studio's capture. The core never knows which transport uses it (the signal pack is one).

    enabled() -> bool                       `remote.enabled`: every transport's switch (on unless you set it false)
    offline() -> bool                       Halo's offline mode is on (a transport that needs the network stays off)
    sessions() -> [row]                     the live sessions, newest first: {session_id, title, cwd, started, kind,
                                            model} (never a token)
    connect(session_id, timeout=10.0)       its control socket (docs/REMOTE.md "The control socket"): a client with
                                            .call(cmd, **fields) -> dict, .next_event(timeout) -> frame | None, .close();
                                            None when the session is not live
    start_session(cwd, model="", by="", timeout_s=45.0) -> (row | None, line)
                                            a session with no terminal started for you (`halo --headless`); with the
                                            supervisor running, the supervisor starts it -- your service never holds
                                            Halo's provider keys
    default_model() -> str                  config `model`
    user_home() -> Path                     the owner's home folder as Halo resolves it
    cards                                   the plain-text cards and the reply parsers (remote/cards.py)
    KINDS, notify(kind, text, source="", session="") -> bool, listen(name), notes(cursor, kinds=None) -> (rows, cursor)
                                            the notes the core gives every transport (remote/notify.py)
    transcribe(path) -> (text | None, line) a WAV voice note through the local speech server that runs (docs/VOICE.md);
                                            another format is converted with ffmpeg when it is on PATH
    qr_text(data) -> str                    a QR code drawn in half-block text
    words() -> tuple                        the 256 words the signing words and pairing phrases use
    service(pack_id, name) -> row | None    a pack service's row as the supervisor last wrote it (supervise/services_rows.py)
    service_ask(pack_id, name, verb) -> line   ask the running supervisor to start or stop one of your services
    logon_lines() -> [line]                 how to start the supervisor (and so the packs' services) at logon here
    live_lines(limit=8) -> [line]           this harness's sessions and what waits on you (API 1.4; fleet_lines its old name)
    capture_studio(session_id="") -> (path | None, line)   a capture of the Halo Studio window when it is open here
"""

from __future__ import annotations

import os
import shutil
from halo_harness import subprocess_safe as subprocess
import tempfile
from pathlib import Path
from typing import Optional

from halo_harness.remote import cards  # noqa: F401  (part of the surface)
from halo_harness.remote.notify import KINDS, listen, notify  # noqa: F401  (part of the surface)

PUBLIC = ("session_id", "title", "cwd", "started", "kind", "model", "pid")


def enabled() -> bool:
    from halo_harness.remote.session_identity import remote_enabled
    return remote_enabled()


def offline() -> bool:
    """Halo's offline mode (`--offline`, HALO_OFFLINE, network.offline): a transport that needs the network stays off."""
    from halo_harness.providers.http import offline_mode_enabled
    return offline_mode_enabled()


def _live() -> list:
    from halo_harness.remote import registry
    try:
        rows = list(registry.list_live())
    except Exception:
        return []
    from halo_harness.newest_first import newest_first
    return newest_first(rows, lambda r: float(r.get("started") or 0))


def sessions() -> list:
    return [{k: r.get(k) for k in PUBLIC} for r in _live()]


def connect(session_id: str, timeout: float = 10.0):
    from halo_harness.remote.client import ControlClient, default_token_for
    entry = next((r for r in _live() if r.get("session_id") == session_id), None)
    if entry is None:
        return None
    return ControlClient(entry["endpoint"], default_token_for(entry), timeout=timeout)


def start_session(cwd, model: str = "", by: str = "", timeout_s: float = 45.0) -> "tuple[Optional[dict], str]":
    from halo_harness.remote import session_start
    entry, line = session_start.start(cwd, model, by, timeout_s)
    return ({k: entry.get(k) for k in PUBLIC} if entry else None), line


def user_home() -> Path:
    """The owner's home folder as Halo resolves it (config/paths.home: the test home under the tests)."""
    from halo_harness.config.paths import home
    return Path(home())


def default_model() -> str:
    from halo_harness.theme import get_config_value
    return str(get_config_value("model", "") or "")


def notes(cursor: str, kinds=None) -> "tuple[list, str]":
    from halo_harness.remote.notify import since
    return since(cursor, kinds)


def _wav(path: Path) -> "tuple[Optional[Path], str]":
    if path.suffix.lower() == ".wav":
        return path, ""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None, f"a {path.suffix or 'voice'} note needs ffmpeg on PATH to be read (it turns it into a WAV)"
    out = Path(tempfile.mkdtemp(prefix="halo-voice-")) / "note.wav"
    try:
        r = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                            str(out)], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        shutil.rmtree(out.parent, ignore_errors=True)
        return None, f"ffmpeg did not convert the note: {type(e).__name__}"
    if r.returncode == 0 and out.is_file():
        return out, ""
    shutil.rmtree(out.parent, ignore_errors=True)
    return None, "ffmpeg did not convert the note"


def transcribe(path) -> "tuple[Optional[str], str]":
    from halo_harness.voice import client, ensure, turn
    url = ensure.running("stt")
    if not url:
        return None, ("no local speech server runs here: `halo local serve --stt` starts one "
                      "(docs/VOICE.md), then voice notes are read")
    wav, why = _wav(Path(path))
    if wav is None:
        return None, why
    try:
        pcm, _secs = turn.pcm_of(wav.read_bytes(), "audio/wav")
        text = client.transcribe(url, pcm)
    except Exception as e:  # the speech server's or the file's trouble, in one line
        return None, f"the note could not be transcribed: {type(e).__name__}: {e}"[:300]
    finally:  # 3.3.14.0 R2 (REVIEW #29, REMOTE-4 / PACKS-7): the converted copy never stays in the temp folder
        if wav != Path(path):
            shutil.rmtree(wav.parent, ignore_errors=True)
    return (text.strip() or None), ("" if text.strip() else "the note held no words the speech server heard")


def qr_text(data: str) -> str:
    from halo_harness.remote.qr import encode
    from halo_harness.remote.qr_render import render
    return render(encode(str(data)))


def words() -> tuple:
    from halo_harness.remote.signing_words import WORDS
    return tuple(WORDS)


def service(pack_id: str, name: str) -> Optional[dict]:
    from halo_harness.supervise.services_rows import row
    return row(f"{pack_id}/{name}")


def service_ask(pack_id: str, name: str, verb: str) -> str:
    """Ask the running supervisor to `start` or `stop` one of a pack's services (its next tick does it); one line."""
    from halo_harness.supervise.services_rows import want
    return want(f"{pack_id}/{name}", verb)


def logon_lines() -> "list[str]":
    from halo_harness.logon_units import SUPERVISOR, enable_command, files_for, os_name
    from halo_harness.supervise import pulse
    from halo_harness.supervise.queue import root
    on = pulse.read()["running"]
    first = "the supervisor runs now" if on else "the supervisor is not running: `halo supervise` starts it"
    how = {"linux": "a systemd user unit", "macos": "a launchd agent", "windows": "a Task Scheduler task at logon"}
    os_n = os_name()
    path = root() / files_for(SUPERVISOR["stem"], SUPERVISOR["label"])[os_n]
    return [first, f"to start it at logon: `halo supervise --service` writes {how[os_n]} ({path.name}) under "
            "~/.halo/supervise/; then this one command turns it on (Halo never runs it):",
            "  " + enable_command(os_n, path, SUPERVISOR["task"])]


def live_lines(limit: int = 8) -> "list[str]":
    """This harness's live sessions and what waits on you (the Attention queue), as lines."""
    from halo_harness.peers import identity
    from halo_harness.live.attention import build
    from halo_harness.peers.local_view import snapshot
    local = snapshot()
    rows = [r for r in local.get("sessions") or [] if isinstance(r, dict)]
    cost = local.get("cost_today")
    out = [f"{local.get('name') or 'This harness'}: {len(rows)} live session(s)"
           + (f", ${cost:.2f} today" if isinstance(cost, (int, float)) else "")]
    for r in rows[:limit]:
        tail = "/".join([p for p in str(r.get("cwd") or "").replace("\\", "/").split("/") if p][-2:])
        out.append(f"  {cards.one_line(r.get('title') or 'untitled', 40)} ({tail}) - {r.get('status') or '?'}")
    waiting = build({"harnesses": [local]}, home=identity.home())
    out.append(f"Waiting on you: {len(waiting)}" + ("" if waiting else " (nothing)"))
    out += [f"  {cards.one_line(w.get('what'), 120)}" for w in waiting[:limit]]
    return out


fleet_lines = live_lines  # API 1.4: its name before 3.5.0.0, still answering
def capture_studio(session_id: str = "") -> "tuple[Optional[str], str]":
    from halo_harness.config.paths import bridge_home
    from halo_harness.studio.launch import port_answers, read_info
    info = read_info(bridge_home()) or {}
    if not info.get("port") or not port_answers(int(info["port"])):
        return None, "Studio is not open on this machine (halo studio opens it)"
    if os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET") and not os.environ.get("HALO_SCREENSHOT_FIXTURE"):
        return None, "no capture under the tests"
    from halo_harness.tools.screenshot import capture_for
    got = capture_for(session_id or None, "window", title="Halo Studio")
    return (str(got["path"]), "") if got.get("ok") else (None, str(got.get("say") or "the capture did not happen"))
