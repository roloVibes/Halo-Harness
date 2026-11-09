"""halo_signal -- the signal pack's code: Halo on your phone through Signal, as a conversation.

It imports `halo_harness.ext` and nothing else of Halo (the extension API; the transport seam is `ext.remote`).
The modules:

    files       the pack's data folder, its JSON files under a lock, the one-time move of ~/.halo/remote/
    settings    the pack's settings (packs.settings.signal) and signal.json (signal-cli's account settings)
    errors, calls, link, transport, typing_keeper   the signal-cli JSON-RPC client
    box         signal-cli and Java on this machine: found, version, the install line
    render      Markdown flattened for a Signal bubble, split, or sent as reply.txt
    signing, ratelimit, audit, pairing, phones      who may talk to Halo and how each phone is set
    bridge, inbound, routing, answers, chat, session, relay, media, notes, outbox   the conversation
    health      the service's health file and stop file
    service     `bin/signal.py service`: the bridge the supervisor keeps running
    ctl         `/signal ...`: status, pair, phones, sign, home, unpair, off, on, link, register, url
    setup       Setup's check blocks
"""

PACK = "signal"
