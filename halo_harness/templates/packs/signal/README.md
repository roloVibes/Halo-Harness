# Signal (signal)

Halo on your phone through Signal, as a conversation: a text starts or continues a session and the answer comes back
paragraph by paragraph; cards are answered from the phone; pictures, PDFs and voice notes go in, files come out; the
supervisor's and the steward's notes arrive when you ask for them. Pair a phone with one six-word text. Runs
signal-cli (GPL-3.0), which you install.

A Halo pack. `HALO-PACK.md` is how to work on it; this page is how to use it. It ships with Halo (`halo pack list
--available`) and stays off until you turn it on. Until Halo 3.3.13.0 it was the core's `halo remote signal` bridge.

## Install

It uses one open-source tool; Halo never installs it, so install it once:

- **signal-cli** (https://github.com/AsamK/signal-cli, GPL-3.0): how this computer speaks Signal. The bridge runs
  it as a child process; the pack carries none of its code.
  - Windows: `winget install EclipseAdoptium.Temurin.25.JRE`, then unpack `signal-cli-<version>.tar.gz` from the
    releases page and add its `bin` folder to PATH (the JVM build needs Java 25)
  - Linux: unpack `signal-cli-<version>-Linux-native.tar.gz` into `~/.local` and put its `bin` folder on PATH (no Java
    needed on x86-64)
  - macOS: `brew install signal-cli`

Setup -> Signal's first block ("Signal on this box") checks it and says the line for your OS. The pack is tested
with signal-cli 0.14.9; Signal changes its servers often, so keep signal-cli under three months old.

## Use it

```
halo pack install signal
halo pack enable signal --grant-all        # services: the bridge runs while the supervisor runs
halo setup signal                          # Setup -> Signal: the box, the account, pairing, the service
halo supervise                             # the bridge starts with it (halo supervise --service: at logon)
```

Then, from a session (`/signal`, no model call) or Setup's pages:

1. **The account.** Either link this computer to your own Signal as a device -- `/signal link` shows a QR code; on the
   phone, Signal -> Settings -> Linked devices -> Link new device, scan it -- and the conversation lives in your
   **Note to Self** chat; or give Halo a number of its own with `/signal register +<number>` (a captcha, then the
   SMS code; Setup's "Or a number of its own" page walks it), and you text Halo like a contact.
2. **Pair the phone.** `/signal pair` shows six words (and a QR code of them) good for ten minutes. Text exactly
   those words from the phone -- to Halo's number, or into Note to Self. That one message pairs it: "Paired." Run
   `/signal pair` again to see "waiting for a text from a new number" or "paired +1...0100".
3. **Talk.** Text "hello". With no session attached, the phone's first text starts one in its home folder ("Starting
   a session in ~/work on <model>.") and the answer follows. The session stays the phone's across restarts.

`/signal` alone shows the bridge (as the supervisor runs it), the account, the phones and the open phrase;
`/signal phones`, `/signal unpair <n>`, `/signal sign on|off <n>`, `/signal home <n> <folder>`, `/signal off` (stop
answering, now) and `/signal on`, `/signal url` (the link that opens the chat with Halo's number), `/signal test` (a
test message to every paired phone), `/signal notices`.

## The conversation

- **A text is a prompt** (a steer while a turn runs). The answer arrives **paragraph by paragraph** as the model writes
  it: one message per paragraph, a code block whole, never cut mid-sentence on a timer. After four messages the rest
  waits and comes at the end as one short message with the whole answer attached as `reply.txt`.
- **While it works** the phone shows Signal's typing indicator, and after 20 seconds with nothing sent one line says
  what it is doing ("still working: ran 3 commands, reading tests/"). A turn that did real work ends with one closing
  line ("Done: ran 3 commands, edited 2 files ($0.04)."); a plain answer is just the answer.
- **Cards are questions.** A permission card: `1` allow once, `2` for the session, `3` always (it names the rule it
  saves), `4` deny (`4 <reason>` tells the model why); a thumbs-up reaction is `1`, a thumbs-down `4`. A question: its
  letter (`b`, or `a,c`), or any text as the answer. A plan: `approve` or `feedback <text>` (thumbs up / down). An
  approval: `accept`, `edit <instruction>` or `stop`. A text that is not an answer while a card waits gets one line
  back -- "A card waits: ... or `send` to pass it to the session" -- and `send` does that.
- **More than text.** A picture goes to the model as the turn's image (one per message). A PDF waits in the pack's
  data folder and the prompt names its path. A **voice note** is transcribed by the local speech server that runs
  here (`halo local serve --stt`, Halo's docs/VOICE.md; ffmpeg reads Signal's .m4a) and sent with "(voice note)" in
  front; with none running, one line says how to turn it on. `/file <path>` sends a file from the session's folder;
  `/shot` sends a capture of the Halo Studio window when Studio is open here.
- **Turns started at the keyboard** reach the phone too while it is `/loud` (the default); `/quiet` keeps only the
  phone's own turns, and then `/notify` decides what else arrives.

### Chat commands

```
/sessions  /attach <n>  /new [folder]  /cd <folder>     which session the phone talks to, where new ones start
/status  /cost  /tail [n]  /stop                        the attached session: state, spend, last lines, interrupt
/mode <name>  /model <ref>  /effort <level>             change it
/fleet                                                  this harness's sessions, the fleet's members, what waits on you
/notify [on|off <kind>]                                 turn_done asks errors supervisor steward
/quiet  /loud  /file <path>  /shot  /signal status|unpair  /help
```

Anything else starting with `/` runs in the session as its own slash command.

### What arrives unprompted (`/notify`)

`asks`: a card or a decision waiting anywhere (the attention queue, while Studio runs its fleet watcher; the attached
session's own cards always arrive). `supervisor`: a goal of `halo supervise` that ended, parked or failed.
`steward`: the Ollama steward's note that asks for attention. `turn_done`: one line when a turn you did not start
ends (with `/quiet`). `errors`. New phones get `asks, errors, supervisor` (the pack's `notify` setting).

## Threat model

The bridge lets a phone do what the keyboard does. These are the layers, what each stops and what it does not.

| # | Layer | Stops | Does not stop |
|---|---|---|---|
| 1 | **Signal's end-to-end encryption** between the phone and this computer (signal-cli holds the keys) | anyone on the network; Signal's servers reading the text | a compromised phone or computer |
| 2 | **Pairing and identity pinning**: a sender is answered only after it texted the open six-word phrase; it is pinned on its Signal account id (ACI), its safety number recorded; a changed safety number blocks it until `/signal reverify` | a stranger who knows the number; a swapped or reinstalled phone | someone who reads the phrase off your screen in its ten minutes; three wrong phrases close it |
| 3 | **Signing (optional, per phone)**: `/signal sign on <n>` makes every message end `#<counter>:<mac>`, an HMAC with a rising counter and a 5-minute window | a device someone else linked to your Signal account (it shares your ACI, not the secret); a replayed message | anyone with the phone and the secret |
| 4 | **At rest**: the data folder's files are 0600; no message text is kept (the audit line is a hash); a file a phone sent is deleted after a day | another account on this machine | root; anyone who can read your account's files (signal-cli's folder holds the Signal keys) |
| 5 | **The local control socket**: loopback only, a token on Windows | other machines and users | another process running as you |
| 6 | **The rate limit and the off switch**: `rate_per_minute` per phone (signed phones' bad messages have their own stricter counter); `/signal off`; `remote.enabled false` stops every transport | a flooding phone; a bridge you want gone now | an owner who is paired: there is no content filter |

**Signing is off by default** for a phone paired by phrase: the Signal session is the channel's own authentication,
and the phrase proves the phone was in your hand. Turn it on for a phone when someone else could read or link it --
a phone you share, a number you do not control, a Signal account with other linked devices you do not trust -- with
`/signal sign on <n>`: the secret is shown once on the computer (32 words, and a `halo-remote://pair` link and QR code
for a signing app) and never sent in the chat.

### Signing

A signed message ends ` #<counter>:<mac>`: `mac` is the first 8 lowercase hex characters of
HMAC-SHA256(key = the 32 secret bytes, data = UTF-8 of "<counter>|<text>"), `<counter>` decimal without leading zeros,
`<text>` the message as typed (trimmed, the trailer removed). The counter must rise; a message more than
`stale_window_s` (300 s) from the clock is refused and its counter used up. Vector: with the secret bytes 0..31
(hex `000102...1e1f`), counter 1 and the text `/status`, the phone sends `/status #1:9ef2aa6c`.

## Running it

The bridge is the pack's **service**: `halo supervise` starts it, starts it again after a crash (5 s, doubling to
300 s), and stops it on its way out; `halo supervise services` lists it, the Pack Manager's row says "running since
09:12" or why it stopped, with Start and Stop. Its health file is `health.json` in the data folder; the TUI's remote
chip says `signal` while it listens. When the supervisor stops, each phone it was talking to gets one line: "No one is
listening on this computer now ..." -- texts sent after that wait on Signal's server until it runs again.

**A VM behind a proxy.** signal-cli asks the JVM for its proxy: use the JVM build and set
`JAVA_TOOL_OPTIONS="-Dhttps.proxyHost=proxy.example.invalid -Dhttps.proxyPort=3128"` where `halo supervise` starts
(`halo supervise --service` carries it into the systemd unit or launchd plist; on Windows set it for your user, since
the at-logon task does not carry it). Allow `chat.signal.org`, `cdn.signal.org`,
`cdn2.signal.org`, `cdn3.signal.org`, `storage.signal.org`, `cdsi.signal.org`, `svr2.signal.org` on TCP 443 with
WebSockets. Halo's offline mode keeps the bridge off.

## Settings

Setup -> Signal -> "The conversation", or `halo config set packs.settings.signal.<key> <value>`: `on`,
`rate_per_minute` (30), `verbosity` (loud), `stale_window_s` (300), `pair_ttl_s` (600), `home_dir` (your home
folder), `model` (your default model), `notify` (asks, errors, supervisor). Halo's old `remote.*` keys for these say
their new home in one line.

## Permissions

Each one runs nothing until you grant it (`halo pack enable signal --grant <name>`):

- `services`: runs a program of this pack in the background while the supervisor runs (the bridge)

## Files

- `pack.yaml`: the manifest; `README.md`: this page; `HALO-PACK.md`: working on the pack; `CHANGELOG.md`
- `.claude-plugin/plugin.json`: the plugin half's name; `commands/signal.md`: the entry command /signal (it runs
  `bin/signal.py ctl`)
- `bin/signal.py`: the pack's one program (service, ctl, setup, link-helper); `halo_signal/`: its code
- `setup/about.md`, `setup/number.md`: Setup's two notes
- `tests/`: the pack's own tests, run by `halo pack test signal` (fakes only: no signal-cli, no Signal message)

What lives in the data folder (`~/.halo/packs/.data/signal/`): signal.json and signal-cli/ (the account), peers.json,
invites.json, phones.json, pending.json, audit.jsonl, health.json, service.log, inbox/. A Halo before 3.3.13.0 kept the
Signal files in `~/.halo/remote/`; the service moves them here once and says so in one line.

## Live verification

1. Install signal-cli as Setup -> "Signal on this box" says; the block turns green.
2. "Link this computer to your Signal": scan the QR code from the phone; `/signal` says the account.
3. `/signal pair`, text the six words from the phone: "Paired."
4. `halo supervise` (or `--daemon`); `halo supervise services` says `signal/bridge running since ...`.
5. With no session open, text "hello": "Starting a session in ~ on <model>.", then the answer.
6. Text "run the tests and ask before anything": answer the card with `1` or a thumbs up.
7. Send a voice note (with `halo local serve --stt` running): it arrives as "(voice note) ...".
8. `/notify asks on`, then stop the supervisor and text again: the one line that says no one is listening came first.

## Develop it

`halo pack test .` checks every part in a scratch home and runs `tests/test_*.py`; `halo pack install . --link
--project` makes the installed pack this folder; `halo pack doctor` says what is left.
