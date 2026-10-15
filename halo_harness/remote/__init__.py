"""halo_harness.remote -- remote control of a live halo session (Halo 2.0.9).

Round 2: the per-session control socket (`control_socket`, wire in
`protocol`), the `SessionHandle` it drives (`handle`, `print_handle`), the
event fan-out (`feed`), the sessions registry (`registry`), the process-wide
open/close glue (`runtime`) and a small `client`. Round 3: the Signal transport and
bridge (`signal_*`, `bridge*`, `pairing*`, `signing*`, `render`). Round 4: the CLI
(`cli*`, `signal_install`, `daemon_units`, `qr*`), the `/remote` dialog model
(`dialog_model`), the bridge pulse (`bridge_state`) and the doctor check
(`doctor_check`). Halo 3.0.5.0 (Fleet): every session opens its control
socket unless config `fleet.enabled` is false or the session is private
(`fleet_identity`, `runtime`); the agent-level commands (`agent_control`)
and the Fleet feed frames (`fleet_frames`). The Signal bridge stays off
unless config `remote.enabled` is true.
"""
