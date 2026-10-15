"""halo_harness.fleet.tls -- the hub's self-signed certificate and the pinned
client side (Halo 3.0.5.0 "Fleet" round R2).

TLS is on when the `cryptography` package is importable on the hub (the
`halo-harness[fleet]` extra): the first `serve` writes `cert.pem` and
`key.pem` (0600, an EC P-256 key, ten years) under `<home>/fleet/hub/`, and
its SHA-256 fingerprint (of the DER bytes) goes into the pair code's QR and
the join reply. A joiner needs only the standard library: it connects
without certificate-chain checks and compares the server certificate's
fingerprint with the pinned one, refusing any other. Without
`cryptography` (or with `serve --no-tls`) the hub speaks plain HTTP and
every request is still HMAC-signed with the pair key.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import ssl
from pathlib import Path
from typing import Optional

CERT, KEY = "cert.pem", "key.pem"


def available() -> bool:
    try:
        import cryptography.x509  # noqa: F401
    except Exception:
        return False
    return True


def fingerprint_der(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


def fingerprint_pem(pem: str) -> str:
    return fingerprint_der(ssl.PEM_cert_to_DER_cert(pem))


def short(fp: Optional[str]) -> str:
    """The fingerprint as people compare it: the first 16 hex characters in pairs."""
    fp = (fp or "").lower()
    return ":".join(fp[i:i + 2] for i in range(0, min(len(fp), 16), 2)) if fp else "(none)"


def _generate(cert_path: Path, key_path: Path, name: str) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    from halo_harness.privateio import write_private_atomic
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, (name or "halo-fleet-hub")[:64])])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - _dt.timedelta(days=1))
            .not_valid_after(now + _dt.timedelta(days=3650)).sign(key, hashes.SHA256()))
    key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode("ascii")
    write_private_atomic(key_path, key_pem)
    write_private_atomic(cert_path, cert.public_bytes(serialization.Encoding.PEM).decode("ascii"))


def ensure_cert(directory: Path, name: str = "") -> "Optional[tuple[Path, Path, str]]":
    """`(cert, key, fingerprint)`, generating them on first use; None when
    `cryptography` is missing and no certificate exists yet."""
    directory = Path(directory)
    cert_path, key_path = directory / CERT, directory / KEY
    if not (cert_path.is_file() and key_path.is_file()):
        if not available():
            return None
        directory.mkdir(parents=True, exist_ok=True)
        _generate(cert_path, key_path, name)
    return cert_path, key_path, fingerprint_pem(cert_path.read_text(encoding="ascii"))


def server_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert_path), str(key_path))
    return ctx


def client_context() -> ssl.SSLContext:
    """No chain or hostname checks: the pinned fingerprint is the check (`check_pin`)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class PinMismatch(ssl.SSLError):
    pass


def peer_fingerprint(sock) -> str:
    der = sock.getpeercert(binary_form=True) if hasattr(sock, "getpeercert") else None
    if not der:
        raise PinMismatch("the hub sent no certificate")
    return fingerprint_der(der)


def check_pin(sock, expected: Optional[str]) -> str:
    """The peer's fingerprint; PinMismatch when `expected` is set and differs."""
    got = peer_fingerprint(sock)
    if expected and got.lower() != str(expected).lower():
        raise PinMismatch(f"the hub's certificate changed (pinned {short(expected)}, got {short(got)}); "
                          "`halo fleet leave` and join again if the hub was reinstalled")
    return got
