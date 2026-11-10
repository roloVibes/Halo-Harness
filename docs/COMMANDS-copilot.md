# Commands: halo copilot

Read this when you sign in to your work's Microsoft 365 Copilot from a terminal, ask it a question about your mail, meetings, chats or files, or sign out again.

`halo copilot` (3.3.17.0) is the door to your work's Copilot: a conversation with an agent that already holds your
work data, not a token-priced model. Part of [Commands](COMMANDS.md), which lists every part; what Copilot at work is,
how to register the app and every error line are in [PROVIDERS-copilot.md](PROVIDERS-copilot.md). Exit codes: 0
done, 1 could not (one line on stderr saying what is missing and the next step), 2 usage.

`halo copilot` with no verb is `halo copilot status`.

## `halo copilot signin`

```sh
halo copilot signin [--device]
```

Opens Microsoft's sign-in page for `copilot.tenant` with your own app registration (`copilot.client_id`) and prints
the URL too; MFA, conditional access and consent happen on that page. Halo listens once on a `127.0.0.1` port for the
redirect (`http://localhost:<port>`) and waits up to 5 minutes, then says who signed in. The refresh token goes to
the env file as `HALO_SECRET_COPILOT_REFRESH`; access tokens stay in memory.

`--device` prints a code and a URL to type it into on any device (a phone, another machine) and waits for it; Halo
takes this path on its own when no browser can open here (SSH, no `DISPLAY`, `HALO_NO_BROWSER`).

## `halo copilot signout`

```sh
halo copilot signout
```

Removes `HALO_SECRET_COPILOT_REFRESH` from the env file, forgets the access token and the account record
(`~/.halo/copilot/account.json`), and says what it removed.

## `halo copilot status`

```sh
halo copilot status [--json]
```

One fact per line, with no network call: signed in as whom and until when the last access token is valid (or "not
set up" / "not signed in" with the next step), the tenant, the app id, the door (`copilot.api`), web grounding, the
time zone, the last problem when there was one, and the scopes an admin consents to. `--json` gives the same facts as
JSON.

## `halo copilot ask`

```sh
halo copilot ask "<prompt>" [--file <url>]... [--no-web] [--api workiq|graph-beta] [--json]
```

One turn with your work's Copilot: the answer, then its citations numbered (`[1] Budget.xlsx -- https://...`), then
the sensitivity label when the answer has one. `--file` (repeatable) names a OneDrive or SharePoint file by its URL
for Copilot to read; `--no-web` keeps the answer to your work data; `--api` picks the door for this ask (default
`copilot.api`); `--json` prints `{text, citations: [{title, url}], sensitivity, conversation, api}`.

```sh
halo copilot ask "What is on my calendar tomorrow?"
halo copilot ask "Summarize this deck" --file https://pretend-tenant.sharepoint.com/sites/x/Deck.pptx --no-web
```
