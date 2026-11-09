---
description: "Signal: Halo on your phone -- the bridge's state, pairing a phone in one message, the phones, the account"
argument-hint: "[pair | phones | unpair <n> | sign on|off <n> | home <n> <folder> | off | on | url | test | link | register | notices]"
run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/bin/signal.py", "ctl"]
---
/signal is the signal pack's own command: it runs the pack's program (bin/signal.py ctl) and shows its answer, with
no model call. With no words it shows the bridge's state, the account and the paired phones; `/signal pair` makes the
six-word phrase a phone texts to pair. The pack's README has the rest.
