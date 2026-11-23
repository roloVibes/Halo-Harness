"""tests.helpers.his_agent -- 3.6.0.15 O2-6: an agent that ships with Halo opened by name is read in the Agents form (its
fields and MODEL picker off, no Save). A browser check of the form's MODEL picker (`&agent=coder`) opens HIS coder: the
shipped file copied under its own name into the scratch home. Imports nothing that touches the environment."""
from __future__ import annotations


def his_coder(state) -> None:
    from halo_harness.crew import store
    got = store.find("agent", "coder", state_dir=state, scope="starter")
    assert got is not None, "the shipped coder"
    store.write_text(store.path_for("agent", "coder", state_dir=state), got[0].read_text(encoding="utf-8"))
