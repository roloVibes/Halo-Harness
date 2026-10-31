"""halo_harness.host -- `halo host` (Halo 3.3.7.0 R1): the model-free Halo process on the machine that serves models.

The host serves, senses and reports; it never loads a model, never runs one, and never carries a prompt body to a
peer. `service.py` is the process (the steward's watch, the resources sampler, the ledger forwarder to a joined hub,
the listener), `state.py` its files and config, `http.py` the signed `/host/v1/` routes, `routes_view.py` the `view`
answers, `answers.py` the fit simulation and the routing answer, `join.py` a peer's half of pairing. docs/HOST.md.
"""
