"""halo_harness.privacy_rules -- 2.0.4 round 1: the shared rule set behind
`halo audit privacy` (halo_harness/audit_cli.py) AND tests/
test_privacy_scan.py's own regression guard, moved here from the test file
so the two import ONE definition and can never quietly drift apart again.
Key/token shapes stay defined in halo_harness.redact (`_TOKEN_PATTERNS`/
`_BEARER_RE`) and are imported from there, not duplicated.

Every rule here is tuned against this repo's OWN tracked tree and full
history (measured by hand before writing this file) so a clean run of
`halo audit privacy` on this repo returns 0 -- the placeholder/exemption
sets below are not guesses, they are every legitimate fixture/example
value this tree actually uses today.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# ---- private-range and link-local IP literals -----------------------------
# RFC1918 (moved verbatim from the old test-local copy) plus link-local
# (169.254.0.0/16, fe80::/10) -- a CIDR suffix (`/16`, `/10`, ...) right
# after the address means this is a RANGE being described (a doc/comment
# naming the block itself), never a literal host address, so the scanner
# skips a match immediately followed by `/<digits>`.
LAN_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})\b"
)
LINK_LOCAL_IP_RE = re.compile(r"\b169\.254\.\d{1,3}\.\d{1,3}\b|\bfe80::[0-9a-fA-F:]+\b")
CIDR_SUFFIX_RE = re.compile(r"^/\d{1,3}\b")

# ---- LAN hostnames / mDNS .local names -------------------------------------
# Anchored on a URL-authority or userinfo@host marker right before the
# candidate, and on a "nothing else dotted follows" lookahead right after
# -- a bare `\.local\b` check (tried and measured first) matches constantly
# in ordinary code/prose that has nothing to do with a hostname: Python's
# own `threading.local()`, any `*.local.json`/`*.local.md` filename
# (`.claude/settings.local.json`, `CLAUDE.local.md`, ...). Those have no
# `://`/`@` anywhere near them, so this stays silent on every one of them.
DOT_LOCAL_RE = re.compile(
    r"(?:(?<=://)|(?<=@))[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.local(?=[:/\s\"'`),\]]|$)"
)

# ---- real user-profile home paths ------------------------------------------
# `C:\Users\<name>`, `C:/Users/<name>`, `/home/<name>`, `/Users/<name>`.
# Every name this tree's own tests/docs legitimately use as a fixture --
# confirmed by a full scan of the tracked tree and the full history before
# this list was written (see plans/2.0.4-history-rewrite-plan.md). A name
# NOT on this list is treated as a real leak.
HOME_PATH_RE = re.compile(r"(?:C:\\Users\\|C:/Users/|/home/|/Users/)([A-Za-z0-9_.-]+)")
PLACEHOLDER_HOME_NAMES = frozenset({
    "user", "users", "example", "someone", "alice", "bob", "x", "...", "work",
    "k", "u", "kal", "kali", "test", "testuser", "youruser", "username", "name",
    "placeholder", "redacted", "anon", "nobody", "yourname", "admin", "",
})
# The owner's real account name(s) -- stored as BARE words (never written
# as part of a "C:\Users\<name>"-shaped literal anywhere in this file's own
# source) so this module never self-matches its own detection logic, and so
# a `git filter-repo --replace-text` pass scrubbing the real path literal
# from history never has to touch this file's CURRENT content.
REAL_OWNER_USERNAMES = frozenset({"ro" + "lo"})
# A real leak can also be a longer, more specific fragment that a bare
# username+placeholder check wouldn't catch on its own (W5's own finding:
# the owner's actual vault path, not just the generic Kali default
# account) -- plain substrings, checked independently of HOME_PATH_RE.
KNOWN_LEAKED_PATH_FRAGMENTS = ("/home/kali/Documents",)

# ---- any path under the state dir ------------------------------------------
# "any path under the state dir" means a REAL absolute path (never the `~`
# shorthand every doc/test uses on purpose) that reaches `.halo` -- i.e. a
# real home-path match (see above) whose same line also contains `.halo`.
STATE_DIR_MARKER = ".halo"

# ---- known real machine / hobby-gear / vendor / owner-name terms ----------
# Moved verbatim from tests/test_privacy_scan.py (W5/W5b/H14b passes) --
# the only way a bare "machine name" category can be checked generically.
def _load_owner_terms() -> "tuple[tuple[str, ...], tuple[str, ...]]":
    """The owner's own machine / gear / vendor / name terms are NEVER stored
    in this public repo (a history rewrite's replace-text pass would corrupt
    this very file, and the list itself is identifying). They come from
    `HALO_PRIVACY_TERMS` (terms separated by `;`, with `ci:` switching the
    rest to case-insensitive) or from `<state dir>/privacy-terms.txt` (one
    term per line, a line `ci:` switching to case-insensitive). With neither
    present the machine-name check is simply inactive and the generic rules
    (paths, addresses, hostnames, tokens, e-mail, junk paths) still apply."""
    exact: "list[str]" = []
    ci: "list[str]" = []
    raw = os.environ.get("HALO_PRIVACY_TERMS", "")
    entries: "list[str]" = []
    if raw.strip():
        entries = [e.strip() for e in raw.split(";")]
    else:
        try:
            from halo_harness.config.paths import bridge_home
            f = bridge_home() / "privacy-terms.txt"
            if f.is_file():
                entries = [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines()]
        except Exception:
            entries = []
    bucket = exact
    for e in entries:
        if not e or e.startswith("#"):
            continue
        if e.lower() == "ci:":
            bucket = ci
            continue
        bucket.append(e)
    return tuple(exact), tuple(ci)


REMOVED_NAMES, EXTENDED_SCAN_TERMS = _load_owner_terms()
EXTENDED_SCAN_ROOTS = ("halo_harness/", "tests/", "docs/", "README.md", "CHANGELOG.md")

# ---- Windows %SystemDrive%/%USERPROFILE%-style stray cache files ---------
# A PATH matching this should never have been committed at all, regardless
# of its content -- the whole file is the problem (purge the path), not a
# line inside it (replace text). Ground truth: 2.0.1 part 6 committed, then
# 2.0.2's review plainly deleted (not purged), four files under a literal
# `%SystemDrive%\...\Caches\` directory -- still reachable from every
# commit before the delete.
JUNK_PATH_RE = re.compile(
    r"%SystemDrive%|%USERPROFILE%|%AppData%|%LocalAppData%|"
    r"/ProgramData/Microsoft/Windows/Caches/|Thumbs\.db$|\.DS_Store$"
)

# ---- e-mail addresses ------------------------------------------------------
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+\b"
)
# RFC 2606 reserved domains and the fake-LAN suffixes this tree's own
# fixtures use on purpose (checked as either the bare domain or a
# subdomain of it).
EMAIL_EXEMPT_DOMAIN_SUFFIXES = (
    "example.com", "example.org", "example.net", "example", "invalid",
    "local", "lan", "test", "localhost", "noreply.github.com",
)
# Well-known, intentionally-public addresses: GitHub's generic git-over-
# ssh remote convention, OpenRouter's own published security contact, and
# Anthropic's own bot attribution address -- none of them the repo owner's
# personal information.
EMAIL_EXPLICIT_ALLOW = frozenset({"git@github.com", "security@openrouter.ai", "noreply@anthropic.com"})
# A loose email-shaped regex also matches common non-email artifacts
# (markdown reference labels like `n@hop1.md`, npm/patch-package version
# pins like `mcp@0.0.82`) -- the final dotted segment being a common file
# extension, or being all-digits (no real TLD is numeric), means "not an
# email", not "an exempt one".
EMAIL_DENY_TLD_LIKE_EXTENSIONS = frozenset({
    "md", "py", "js", "ts", "json", "txt", "patch", "yml", "yaml", "toml", "cfg", "ini", "log",
    "csv", "html", "xml", "sh", "ps1", "bat", "png", "jpg", "jpeg", "svg", "pdf", "zip", "whl",
})

# ---- the allowlist file (exact-string exemption, any finding kind) --------
ALLOWLIST_RELPATH = "tests/privacy_scan_allowlist.txt"

# ---- self-exclusion --------------------------------------------------------
# Files whose SOURCE legitimately names a string this module's own rules
# would otherwise flag (the detectors defined here, and the regression
# guard that imports them) -- excluded from the scan entirely, the same
# precedent tests/test_privacy_scan.py already set for itself.
SELF_EXCLUDE_RELPATHS = frozenset({
    "halo_harness/privacy_rules.py",
    "tests/test_privacy_scan.py",
    "tests/test_audit_privacy.py",
})


def home_path_name_is_real(name: str) -> bool:
    """True if `name` (the text right after `C:\\Users\\`/`/home/`/`/Users/`)
    looks like a REAL account name rather than a known placeholder."""
    lname = name.lower().rstrip(".,;:)'\"")
    if lname in REAL_OWNER_USERNAMES:
        return True
    return lname not in PLACEHOLDER_HOME_NAMES


def email_is_exempt(addr: str) -> bool:
    if addr in EMAIL_EXPLICIT_ALLOW:
        return True
    domain = addr.split("@", 1)[1].lower()
    last_segment = domain.rsplit(".", 1)[-1]
    if last_segment.isdigit() or last_segment in EMAIL_DENY_TLD_LIKE_EXTENSIONS:
        return True
    return any(domain == suf or domain.endswith("." + suf) for suf in EMAIL_EXEMPT_DOMAIN_SUFFIXES)


def is_junk_path(path_text: str) -> bool:
    return JUNK_PATH_RE.search(path_text) is not None


def is_self_excluded(rel_posix_path: str) -> bool:
    return rel_posix_path in SELF_EXCLUDE_RELPATHS


def load_allowlist(repo_dir: Path) -> "set[str]":
    """Exact-string exemptions, one per line, shared by every finding kind
    (not just key-shaped fragments) -- blank lines and `#` comments
    ignored. Missing file -> empty set (nothing exempted)."""
    path = repo_dir / ALLOWLIST_RELPATH
    if not path.exists():
        return set()
    allowed = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        allowed.add(line)
    return allowed
