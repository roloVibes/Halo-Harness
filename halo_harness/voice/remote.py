"""halo_harness.voice.remote -- the speech servers of another halo on the LAN, through its `halo host` (Halo 3.3.9.0 R3;
docs/VOICE.md "Through the host"). A box with no GPU (the Mac, Kali) sets `voice.stt_server: stt@pc` / `voice.tts_server:
tts@pc` and its loop hears and speaks with the PC's models; every request is signed with the pair key and goes through
the host's voice routes (host/ops_voice.py), so the speech servers there keep listening on loopback only.

    setting(kind) -> "local" | "<kind>@<host>"        voice.stt_server / voice.tts_server (default local)
    parse(ref) -> the host's name | None (local)      "stt@pc", "tts@pc" and a bare "pc" name the host pc
    client_for(name) -> (HostClient | None, why)      the paired host by its name, else by the Ollama host of that name
    resolve(kind, ref=None) -> {url, host, model, link_ms, line} | {error}   the host lists a speech server of that kind
        (its join's or announce's served rows, `kind: speech`; else `GET me`'s voice block); the link is the TCP round
        trip to the host's port, measured as 3.3.8.1 measures a LAN bench (providers/rpc_probe.probe)
    is_remote(url) / transcribe(url, pcm, rate) / speak(url, text, voice)   voice/client.py hands a `halo-host:` url here
    turn(c, body, ctype, session="", voice="") -> iterator of (kind, payload)   the voice door (`halo voice client`)

A missing host, server or grant is one line with the command that fixes it; nothing retries by itself.
"""

from __future__ import annotations

import http.client
import json
import struct
from typing import Iterator, Optional

PREFIX = "halo-host:"
_CLIENTS: dict = {}  # url -> HostClient (the resolve that made it)
CHUNK = 4800


def setting(kind: str) -> str:
    from halo_harness.theme import get_config_value
    v = get_config_value(f"voice.{kind}_server", default=None)
    return str(v).strip() if isinstance(v, str) and v.strip() else "local"


def parse(ref) -> Optional[str]:
    r = str(ref or "").strip()
    if not r or r.lower() == "local":
        return None
    return r.split("@", 1)[1].strip() or None if "@" in r else r


def _join_line(name: str) -> str:
    return (f"no paired halo host named {name}: on {name}, `halo host serve` and `halo host pair`; here, `halo host join "
            f"<its address> <code>`")


def client_for(name: str, home=None):
    from halo_harness.peers import identity, store
    from halo_harness.ollama_steward.host_client import HostClient, for_host
    want = name.lower()
    for e in store.hosts(home):
        if e.get("state", "joined") != "joined":
            continue
        names = {str(e.get("name") or "").lower(), str(e.get("name") or "").lower().split("@")[0]}
        if want in names:
            key = store.key_for(e, home)
            return (HostClient(e, key, identity.harness()["id"]), "") if key else (None, _join_line(name))
    try:
        from halo_harness.providers.ollama import resolve_ollama_host
        h = resolve_ollama_host(name)
        if h is not None and h.name.lower() == want:
            c = for_host(h, home)
            if c is not None:
                return c, ""
    except Exception:
        pass
    return None, _join_line(name)


def link_ms(c) -> Optional[float]:
    try:
        from halo_harness.providers.rpc_probe import probe
        got = probe(c.host, c.port)
        return got.get("rtt_ms") if got.get("alive") else None
    except Exception:
        return None


def _row(c, kind: str) -> Optional[dict]:
    rows = [r for r in c.entry.get("servers") or [] if isinstance(r, dict) and r.get("kind") == "speech"
            and r.get("runtime") == f"voice-{kind}"]
    if rows:
        return rows[0]
    from halo_harness.ollama_steward.host_client import HostError
    try:
        got = (c.me(fresh=True).get("voice") or {}).get(kind)
    except HostError:
        return None
    return got if isinstance(got, dict) else None


def resolve(kind: str, ref: Optional[str] = None, home=None) -> dict:
    name = parse(setting(kind) if ref is None else ref)
    if name is None:
        return {"error": f"voice.{kind}_server is local: this machine's {kind} server"}
    c, why = client_for(name, home)
    if c is None:
        return {"error": why}
    row = _row(c, kind)
    if row is None:
        model = "faster-whisper:small.en" if kind == "stt" else "kokoro-82m"
        return {"error": f"{name} lists no {kind} server: on {name}, halo local serve --{kind} {model} (the halo host "
                         f"there shares it)", "host": name}
    ms = link_ms(c)
    url = f"{PREFIX}{name}#{kind}"
    _CLIENTS[url] = c
    word = "?" if ms is None else (f"{ms:.0f}" if ms >= 10 else f"{ms:.1f}")
    return {"url": url, "host": name, "model": row.get("model"), "link_ms": ms,
            "line": f"{kind} on {name} over the LAN (+{word} ms)" + (f": {row['model']}" if row.get("model") else "")}


def is_remote(url) -> bool:
    return str(url or "").startswith(PREFIX)


def _client(url: str):
    from halo_harness.voice.client import VoiceError
    c = _CLIENTS.get(url)
    if c is None:
        name = url[len(PREFIX):].split("#", 1)[0]
        c, why = client_for(name)
        if c is None:
            raise VoiceError(why)
        _CLIENTS[url] = c
    return c


def _post(c, route: str, body: bytes, ctype: str, timeout: float = 60.0):
    """(conn, response) of one signed POST to /host/v1/<route>; VoiceError with the host's line otherwise."""
    from halo_harness.peers import protocol, tls
    from halo_harness.peers.relay import HubError, _connect
    from halo_harness.voice.client import VoiceError
    path = "/host/v1/" + route
    headers = {**protocol.sign_headers(c.key, "POST", path, c.member, body), "Content-Type": ctype,
               "Content-Length": str(len(body))}
    try:
        conn, _ = _connect(c.scheme, c.host, c.port, timeout, c.entry.get("fingerprint"))
        conn.request("POST", path, body=body, headers=headers)
        r = conn.getresponse()
    except (HubError, tls.PinMismatch, OSError, http.client.HTTPException) as e:
        raise VoiceError(f"the {c.label} did not answer: {e}") from None
    if r.status != 200:
        try:
            msg = json.loads(r.read().decode("utf-8") or "{}")
        except ValueError:
            msg = {}
        conn.close()
        err = msg.get("error") if isinstance(msg, dict) else None
        raise VoiceError(str((err or {}).get("message") if isinstance(err, dict) else err or
                             f"the {c.label} answered {r.status}"))
    return conn, r


def transcribe(url: str, pcm16: bytes, rate: int = 16000) -> str:
    conn, r = _post(_client(url), "voice/stt", pcm16, f"audio/pcm;rate={int(rate)}")
    try:
        return str(json.loads(r.read().decode("utf-8") or "{}").get("text") or "").strip()
    except ValueError:
        return ""
    finally:
        conn.close()


def _chunks(conn, r) -> Iterator[bytes]:
    left = b""
    try:
        while True:
            b = left + r.read(CHUNK)
            if len(b) == len(left):
                return
            cut = len(b) // 2 * 2
            left = b[cut:]
            if cut:
                yield b[:cut]
    except (OSError, http.client.HTTPException):
        return
    finally:
        conn.close()


def speak(url: str, text: str, voice: str) -> "tuple[int, Iterator[bytes]]":
    body = json.dumps({"input": text, "voice": voice, "response_format": "pcm"}).encode("utf-8")
    conn, r = _post(_client(url), "voice/tts", body, "application/json")
    return int(r.getheader("X-Sample-Rate") or 24000), _chunks(conn, r)


def _exact(r, n: int) -> bytes:
    out = b""
    while len(out) < n:
        b = r.read(n - len(out))
        if not b:
            break
        out += b
    return out


def turn(c, body: bytes, ctype: str, session: str = "", voice: str = "", timeout: float = 600.0):
    """The voice door: [(kind "J" | "A" | "N", payload)] as the host streams them (J and N payloads decoded): J
    {heard}, J {rate}, A <PCM16>..., N {note}, J {done, ...} (host/ops_voice.py has the shape)."""
    import urllib.parse
    q = urllib.parse.urlencode({k: v for k, v in (("session", session), ("voice", voice)) if v})
    conn, r = _post(c, "voice/turn" + (f"?{q}" if q else ""), body, ctype, timeout)

    def frames():
        try:
            while True:
                head = _exact(r, 5)
                if len(head) < 5:
                    return
                kind, n = head[:1].decode("ascii", "replace"), struct.unpack(">I", head[1:])[0]
                payload = _exact(r, n)
                yield kind, (payload if kind == "A" else json.loads(payload.decode("utf-8") or "{}"))
        finally:
            conn.close()
    return frames()
