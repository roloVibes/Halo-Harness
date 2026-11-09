# Signal on your phone

With this pack Halo answers you on Signal. You text it, and a session on this computer does the work and answers
paragraph by paragraph; when a tool needs your yes, the card comes to the phone and you answer with `1`, a letter or
a thumbs up. A picture, a PDF or a voice note goes to the session too, and `/file <path>` brings a file back.

Four steps, in order, on this page:

1. **Signal on this box** -- signal-cli is the program that speaks Signal for this computer. Halo never installs it;
   the check says the one line for your OS.
2. **The account** -- either link this computer to your own Signal as a device (the next block shows a QR code to
   scan; the conversation is then your *Note to Self* chat), or give Halo a number of its own (the block after it).
3. **Pair a phone** -- one six-word phrase, texted once from the phone. Signing stays off: the Signal session itself
   is what proves a message is your phone's. The README's "Threat model" says when to turn signing on.
4. **The service** -- the bridge runs while Halo's supervisor runs (`halo supervise`). The last block says whether it
   runs now and how to start the supervisor when you log in.

What leaves this computer: the replies you asked for, as Signal messages, end-to-end encrypted by Signal. What stays:
the paired phones, a hashed line per message in `audit.jsonl`, and files a phone sent (deleted after a day), in the
pack's data folder. `/signal off` stops it answering at once.
