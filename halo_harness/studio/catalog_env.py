"""halo_harness.studio.catalog_env -- the environment Studio's model catalog
resolves providers with (Halo 3.1.4.0 R4).

The owner's live check of 3.1.3.0 on Kali: the TUI session ran on
`dbx:databricks-glm-5-3` while Studio's Models panel said "No provider is set
up in this Halo home yet". The session resolves providers through
`Settings.effective_env` (the env file, then the shell < user < trusted
project/local < policy settings.json `env` chain, headless.build_session);
Studio's catalog built `dict(os.environ)` -- a COPY, so every resolver's
settings-chain fallback (gated on `env is os.environ`) was skipped, and a key
that lives in a settings.json `env` block (a Databricks gateway's
ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN, DATABRICKS_HOST / TOKEN) never
counted. `catalog_env(cwd)` is the session's resolution: the env file loaded,
then `providers.config.listing_effective_env(cwd)` (the same chain, trust-aware).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def catalog_env(cwd: "Optional[Path | str]" = None) -> dict:
    """The env file, then the settings chain a session in `cwd` resolves (a fresh dict)."""
    from halo_harness.providers.config import listing_effective_env, load_provider_env_files
    load_provider_env_files()
    return dict(listing_effective_env(Path(cwd) if cwd else None))
