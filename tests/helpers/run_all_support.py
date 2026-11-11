"""tests.helpers.run_all_support -- what tests/run_all.py does around each
module (Halo 3.1.0.0 round R1), kept here so run_all.py stays readable:

* 3.3.8.1: the shard of a module (`--shard i/n`: its index in the sorted
  discovered list mod n; `--shard-of tests.test_x` names it), composing with
  the tier;
* the tier of a module (`TIER = "full"` near the top of the file: it needs
  Chrome or a TUI pilot; every other module is "fast"), read with a regex
  over the file head, never by importing the module;
* the module's own scratch home: a fresh `BRIDGE_TEST_HOME` per module, a
  subdirectory of the run's scratch root named after the module, set before
  the module is imported and removed after it;
* the module-level caches that key on the state dir (or hold a "done once
  for this home" flag) reset between modules, so nothing one module's home
  put in memory is read back under the next module's home.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

TIERS = ("fast", "full")
_TIER_RE = re.compile(r"""^TIER\s*=\s*["'](fast|full)["']\s*(?:#.*)?$""", re.MULTILINE)
_HEAD_BYTES = 16 * 1024  # the docstring, the imports and the TIER line all sit inside this


def module_tier(path: Path) -> str:
    """`"full"` when the file head declares `TIER = "full"`, else `"fast"`.
    Reads at most the first 16 KB; never imports the module."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(_HEAD_BYTES)
    except OSError:
        return "fast"
    m = _TIER_RE.search(head)
    return m.group(1) if m else "fast"


def select_tier(paths: "list[Path]", tier: "str | None") -> "list[Path]":
    """The modules a run with `--tier <tier>` covers (`None` = every module)."""
    if tier is None:
        return list(paths)
    return [p for p in paths if module_tier(p) == tier]


def parse_tier_args(argv: "list[str]") -> "str | None":
    """`--fast` = the fast tier, `--tier fast|full`, nothing = every module.
    Raises ValueError on anything else."""
    tier = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--fast":
            tier = "fast"
        elif arg == "--tier" and i + 1 < len(argv):
            tier = argv[i + 1]
            i += 1
        elif arg.startswith("--tier="):
            tier = arg.split("=", 1)[1]
        else:
            raise ValueError(f"unknown argument {arg!r} (use --fast, --tier fast or --tier full)")
        i += 1
    if tier is not None and tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r} (fast or full)")
    return tier


SHARDS = 4  # 3.3.8.1: the CI matrix's shard count (.github/workflows/suites.yml), the default of --shard-of


def parse_run_args(argv: "list[str]") -> dict:
    """{tier, shard: (i, n) | None, shard_of: name | None, shards: n}: the tier flags (parse_tier_args) plus 3.3.8.1's
    `--shard i/n` (the modules whose index in the sorted discovered list is i mod n) and `--shard-of tests.test_x
    [--shards n]` (prints that module's shard). Raises ValueError on anything else."""
    rest, shard, of, n = [], None, None, SHARDS
    i = 0
    while i < len(argv):
        arg, nxt = argv[i], (argv[i + 1] if i + 1 < len(argv) else None)
        if arg in ("--shard", "--shard-of", "--shards") and nxt is None:
            raise ValueError(f"{arg} needs a value")
        if arg == "--shard" or arg.startswith("--shard="):
            shard = parse_shard(nxt if arg == "--shard" else arg.split("=", 1)[1])
            i += 2 if arg == "--shard" else 1
        elif arg == "--shard-of":
            of, i = nxt, i + 2
        elif arg == "--shards":
            if not str(nxt).isdigit() or int(nxt) < 1:
                raise ValueError(f"--shards takes a count, got {nxt!r}")
            n, i = int(nxt), i + 2
        else:
            rest.append(arg)
            i += 1
    return {"tier": parse_tier_args(rest), "shard": shard, "shard_of": of, "shards": n}


def parse_shard(text: str) -> "tuple[int, int]":
    m = re.fullmatch(r"(\d+)/(\d+)", str(text or "").strip())
    if not m or int(m.group(2)) < 1 or int(m.group(1)) >= int(m.group(2)):
        raise ValueError(f"--shard takes i/n with 0 <= i < n, got {text!r}")
    return int(m.group(1)), int(m.group(2))


def select_shard(names: "list[str]", shard: "tuple[int, int] | None", every: "list[str] | None" = None) -> "list[str]":
    """`names` narrowed to the shard: a module's index in `every` (the sorted discovered list; default `names`) mod n."""
    if shard is None:
        return list(names)
    i, n = shard
    index = {name: k for k, name in enumerate(sorted(every if every is not None else names))}
    return [name for name in names if index.get(name, -1) % n == i]


def shard_of(name: str, every: "list[str]", n: int = SHARDS) -> "str | None":
    """'2/4': the shard that runs `name` (tests.test_x or test_x), None when it is not a discovered module."""
    full = name if name.startswith("tests.") else f"tests.{name}"
    ordered = sorted(every)
    return f"{ordered.index(full) % n}/{n}" if full in ordered else None


def tier_label(tier: "str | None") -> str:
    if tier == "fast":
        return "fast (no Chrome, no TUI pilots)"
    if tier == "full":
        return "full (the Chrome and TUI pilot modules only)"
    return "all (fast + full)"


def make_run_root() -> Path:
    """The run's scratch root for the per-module homes: under the caller's
    own `BRIDGE_TEST_HOME` when one is set (CI's fresh test home, a
    developer's scratch dir), else a temp dir. Made with `tempfile.mkdtemp`,
    so run_all's `[cleanup]` step removes whatever is left of it."""
    # Always the system temp dir (/tmp on Linux, the runner's TEMP on Windows), never under the caller's
    # BRIDGE_TEST_HOME: a Unix socket path under a module's home must stay under Linux's 108-byte AF_UNIX
    # limit, and the CI test-home root alone is 39 characters (two red runs: "AF_UNIX path too long").
    # run_all's [cleanup] removes whatever is left of it (it tracks every mkdtemp).
    return Path(tempfile.mkdtemp(prefix="hra-"))


def module_home_name(mod_name: str) -> str:
    """`tests.test_x` -> `test_x` (a plain directory name); a name past 24 characters is cut and tagged with
    four hex characters of its hash so the home stays short (the AF_UNIX limit above) and unique."""
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", mod_name.split(".")[-1]) or "module"
    if len(name) <= 24:
        return name
    import hashlib
    return f"{name[:19]}-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:4]}"


def enter_module(run_root: Path, mod_name: str) -> Path:
    """Point this process at a fresh home for `mod_name`: `BRIDGE_TEST_HOME`
    set, any `BRIDGE_STATE_DIR` dropped, the state-dir caches reset, and
    `ensure_scoped_state_dir_once` told which module now runs."""
    home = run_root / module_home_name(mod_name)
    if home.exists():
        shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    reset_state_caches()
    from tests.helpers import provider_env_defaults
    provider_env_defaults.begin_module(mod_name, home)
    return home


def leave_module(home: Path) -> bool:
    """Forget the module and remove its home (best effort: a file a
    background thread still holds open on Windows stays for `[cleanup]`).
    True when the directory is gone."""
    from tests.helpers import provider_env_defaults
    provider_env_defaults.end_module()
    reset_state_caches()
    shutil.rmtree(home, ignore_errors=True)
    return not home.exists()


def _loaded(name: str):
    """The module if it is already imported, else None (never imports one)."""
    return sys.modules.get(name)


def _clear(module_name: str, attr: str) -> bool:
    mod = _loaded(module_name)
    value = getattr(mod, attr, None) if mod is not None else None
    if hasattr(value, "clear"):
        value.clear()
        return True
    return False


def _call(module_name: str, fn_name: str) -> bool:
    mod = _loaded(module_name)
    fn = getattr(mod, fn_name, None) if mod is not None else None
    if callable(fn):
        try:
            fn()
            return True
        except Exception:
            return False
    return False


# (module, attribute or function, what it holds). Each one is either keyed on
# the state dir / a path inside it, or a "done once" flag for this process's
# home that a later module's fresh home must not inherit.
STATE_CACHES = (
    ("halo_harness.config.paths", "_state_dir_memo", "bridge_home()'s first resolution per home()"),
    ("halo_harness.providers.databricks", "_DBX_ROUTE_CACHE", "routes-cache.json merged in memory from whichever state dir read it first"),
    ("halo_harness.peers.identity", "_cache", "config.json per path, one-second TTL"),
    ("halo_harness.peers.catalog", "_loaded", "the capabilities catalog per path and mtime (3.4.0.0 C: core peers/)"),
    # 3.4.0.0 D: the fleet pack's health module, by the name the pack registry imports it under (halo_packs.<id>)
    ("halo_packs.fleet.fleet.health", "_cache", "the health subset (disk of bridge_home(), providers), 60 s TTL"),
    ("halo_harness.peers.local_view", "_cache", "this home's registry sessions and their status"),
    ("halo_harness.studio.sessions_api", "_cache", "the live sessions of this home's registry"),
)
STATE_RESETS = (
    ("halo_harness.mcp.connectors_bridge", "reset_session_state", "the once-per-process connector discovery flag (its cache file lives in the state dir)"),
    # 3.3.8.1: the url-keyed caches a mock on a reused 127.0.0.1 port would be answered from in the NEXT module (the
    # shards changed which modules neighbour which; both mocks reset these on start too, this is the harness-level half)
    ("halo_harness.providers.ollama", "reset_catalog_cache", "the per-url Ollama catalog (TTL + last good entry)"),
    ("halo_harness.providers.huggingface_local_resolve", "reset_local_probe_cache", "the per-url context-length readback (30 s)"),
    ("halo_harness.providers.huggingface_local_probe", "reset_auto_detect_cache", "the auto-detected local servers by probed port (60 s)"),
    # 3.4.0.0 (the B2 + C merge moved shard neighbours): a fake runner's GPU kept for the TTL answered the next module's
    # "no GPU" runner (test_providers_ollama_panel after test_local_fit's cards)
    ("halo_harness.providers.ollama_hw", "reset_local_gpu_cache", "this machine's GPU reading(s), one TTL slot"),
    ("halo_harness.providers.ollama_hw", "reset_ssh_gpu_cache", "a host's GPU over ssh, per user@host, one TTL slot"),
)


def reset_state_caches() -> "list[str]":
    """Clear every cache in STATE_CACHES / STATE_RESETS whose module is
    already imported; returns the `module.attr` names it cleared."""
    done = []
    for module_name, attr, _why in STATE_CACHES:
        if _clear(module_name, attr):
            done.append(f"{module_name}.{attr}")
    for module_name, fn_name, _why in STATE_RESETS:
        if _call(module_name, fn_name):
            done.append(f"{module_name}.{fn_name}()")
    return done
