# Changelog: Signal (signal)

Each release of the pack, newest first: the version (pack.yaml's `version`), the date, what changed for the person
who runs it. A change they must act on also gets a `migrations` entry in pack.yaml.

## 1.0.0 - unreleased (ships with Halo 3.3.13.0)

- The Signal bridge leaves Halo's core (`halo remote signal`) and becomes this pack, and a conversation:
  - it runs as a service the supervisor keeps running (`halo supervise`), not a terminal you keep open;
  - pairing is one six-word text (`/signal pair`); signing is optional per phone (`/signal sign on <n>`);
  - a text with no session starts one in the phone's home folder; the phone keeps its session across restarts;
  - the answer arrives paragraph by paragraph, with one closing line only after real work, and a status line while
    tools run;
  - pictures, PDFs and voice notes go in; `/file` and `/shot` come out; a thumbs up answers a card;
  - `/notify` chooses what arrives unprompted (the attention queue, the supervisor's and the steward's notes);
  - `/signal` and Setup -> Signal replace `halo remote signal setup | register | link | run | pair | peers | unpair |
    reverify | status | off | on` and the TUI's `/remote` dialog.
- The files of `~/.halo/remote/` (signal.json, signal-cli/, peers.json, pending.json, audit.jsonl, the
  registration PIN) move into the pack's data folder once, on the service's first start. Phones paired before keep
  their pairing and their signing.
- Halo no longer downloads signal-cli for you: install it as the README says (`requires:`).
