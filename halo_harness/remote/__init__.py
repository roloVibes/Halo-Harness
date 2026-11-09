"""halo_harness.remote -- remote control of a live halo session (Halo 2.0.9).

Round 2: the per-session control socket (`control_socket`, wire in
`protocol`), the `SessionHandle` it drives (`handle`, `print_handle`), the
event fan-out (`feed`), the sessions registry (`registry`), the process-wide
open/close glue (`runtime`) and a small `client`. Round 3/4 added the Signal bridge,
which left the core in 3.3.13.0 R3 for the signal pack (halo_harness/templates/packs/signal);
what it shared stays: the cards' text (`cards`), the QR drawing (`qr*`), the word list
(`signing_words`), the small CLI helpers (`cli_common`), the locked JSON files
(`pairing_files`), the process identity (`proc_ident`). Halo 3.0.5.0 (Fleet): every
session opens its control socket unless config `fleet.enabled` is false or the session is
private (`fleet_identity`, `runtime`); the agent-level commands (`agent_control`) and the
Fleet feed frames (`fleet_frames`). 3.3.13.0 R3, the transport seam a pack's bridge uses
(through `halo_harness.ext.remote`): the notes every transport may carry (`notify`,
`notify_sources`), a session started for a transport (`session_start`), `/remote` and the
chip (`status`), the doctor rows (`doctor_check`); `remote.enabled` is every transport's switch.
"""
