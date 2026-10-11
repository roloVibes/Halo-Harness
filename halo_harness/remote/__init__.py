"""halo_harness.remote -- remote control of a live halo session (Halo 2.0.9).

Round 2: the per-session control socket (`control_socket`, wire in
`protocol`), the `SessionHandle` it drives (`handle`, `print_handle`), the
event fan-out (`feed`), the sessions registry (`registry`), the process-wide
open/close glue (`runtime`) and a small `client`. The Signal transport and
bridge come in later rounds. Off unless config `remote.enabled` is true.
"""
