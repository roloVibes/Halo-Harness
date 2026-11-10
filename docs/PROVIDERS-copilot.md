# Copilot at work

Read this when you want Halo to use your work's Microsoft 365 Copilot: register the app, sign in, ask it from a terminal, put it in a lineup or give agents the `copilot_ask` tool, and read what each error line means.

Halo 3.3.17.0. The commands are in [COMMANDS-copilot.md](COMMANDS-copilot.md); the settings in
[CONFIG.md](CONFIG.md) (`copilot.*`).

## What it is, and what it is not

Copilot at work is **a conversation with an agent that already holds your work**: your mail, meetings and their
transcripts, Teams chats and channels, OneDrive and SharePoint files, people, and the enterprise search your tenant
has connected, each trimmed to what your account may see. Halo talks to it as you (delegated sign-in), one
conversation per Halo session.

It is **not a token-priced model**. You do not choose its model, it does not call Halo's tools, and it is not billed
per token: the Work IQ API is billed by Copilot Credits on your tenant's consumption plan, the Graph Copilot Chat API
needs a Microsoft 365 Copilot licence per user. Halo never shows a dollar figure for it (see "Costs").

In Halo it appears three ways: `halo copilot ask` on the command line, the model `cp:work` (a session or a lineup role
can run on it), and the tool `copilot_ask` (any agent whose bio or lineup card allows it can ask Copilot and get the
answer with its citations).

## The two doors

| `copilot.api` | What it is | Needs | When it works |
|---|---|---|---|
| `workiq` (default) | The Work IQ API (GA since 2026-06-16): JSON-RPC `SendMessage` to its A2A endpoint, `A2A-Version: 1.0`, the conversation kept by its `contextId` | the Work IQ delegated scope, consented by an admin; consumptive billing (Copilot Credits) enabled for the tenant | production use; no Copilot seat needed |
| `graph-beta` | Graph's `/beta` Microsoft 365 Copilot Chat API: `POST /beta/copilot/conversations`, then `.../{id}/chat` | the seven delegated Graph permissions below, consented; a Microsoft 365 Copilot licence for the user; the global cloud | a preview ("not supported in production"); often the door that works first where Graph is already in use |

Switch with `halo config set copilot.api graph-beta`, or for one ask with `halo copilot ask "..." --api graph-beta`.

## Register the app

Halo signs in with **your own** Entra app registration (no shared app id ships with Halo). Once, in the Entra admin
center (or ask your admin):

1. **Identity -> Applications -> App registrations -> New registration.** Name it (e.g. "Halo on my laptop"),
   "Accounts in this organizational directory only", and no redirect yet. Register.
2. **Authentication -> Add a platform -> Mobile and desktop applications.** Add the custom redirect URI
   `http://localhost` (Entra accepts any port on a loopback redirect for a public client; Halo picks a free one each
   sign-in). Under "Advanced settings" set **Allow public client flows: Yes** (the device-code fallback needs it).
   There is no client secret: Halo is a public client and uses PKCE.
3. **API permissions -> Add a permission**, delegated permissions only:
   - for `graph-beta`: Microsoft Graph `Sites.Read.All`, `Mail.Read`, `People.Read.All`,
     `OnlineMeetingTranscript.Read.All`, `Chat.Read`, `ChannelMessage.Read.All`, `ExternalItem.Read.All`;
   - for `workiq`: the Work IQ API's delegated permission (Halo asks for `https://workiq.svc.cloud.microsoft/.default`,
     which requests whatever delegated permission the registration lists for that resource; check Microsoft Learn's
     Work IQ authentication page for its name, and set `copilot.scopes` if your tenant needs a different list).
   Then **Grant admin consent** (an admin does this once for the tenant). `halo copilot status` and Studio's Copilot
   card list the exact scopes to consent to.
4. Copy the **Application (client) ID** and the **Directory (tenant) ID** from the Overview page:

```sh
halo config set copilot.tenant <directory id or yourcompany.onmicrosoft.com>
halo config set copilot.client_id <application id>
```

The docs and tests use `pretend-tenant` and `00000000-0000-0000-0000-000000000000`; nothing in Halo's repo holds a
real tenant, app id or token.

## Sign in

`halo copilot signin` opens Microsoft's sign-in page (MFA, conditional access and consent happen there) and prints its
URL too, then listens once on `127.0.0.1` for the redirect and waits up to 5 minutes. On a box with no browser (SSH, a
headless Kali, `HALO_NO_BROWSER`) or with `--device`, it prints a code and `https://microsoft.com/devicelogin` instead:
type the code on any device. Studio's Setup -> Providers has the same Sign in on its Copilot card.

What is kept: the **refresh token** in the env file as `HALO_SECRET_COPILOT_REFRESH` (never `config.json`, never a log
line, never the transcript); **access tokens** only in memory, refreshed 60 s before they expire; who signed in and
until when in `~/.halo/copilot/account.json` (no token). `halo copilot signout` removes all three.

## Ask from the terminal

```sh
halo copilot ask "What did I agree to in yesterday's meeting with the design team?"
halo copilot ask "Summarize the risks in this plan" --file https://pretend-tenant.sharepoint.com/sites/x/Plan.docx
halo copilot ask "Who owns the Q3 budget?" --no-web --json
```

The answer, then its citations numbered, then the sensitivity label when the answer carries one.

## In a lineup: the model `cp:work`

`cp:work` is "your work's Copilot" as a model reference. Its catalog row says `takes: text, files, web`, `tools: no`,
context window unknown, and the price "Copilot Credits or your licence"; `halo models` lists it once you are signed in.
A session or a lineup role may run on it: each turn goes to the conversation (the session's first turn starts it,
later turns continue it). Because it takes no tools, a role on `cp:work` is a **consult role**: the agent loop offers
it no tools, and Auto never picks it for a role that needs tool calls. Auto does pick it for the need `work-data`
("research over your work data") when you are signed in:

```yaml
# a bio
models: {preference: auto, needs: [work-data]}
```

## The tool `copilot_ask`

`copilot_ask {prompt, files?: [url], web?: bool}` asks Copilot from inside any agent and answers with the text and its
citations as numbered lines; the call and its citations land in the transcript like any tool result. It is registered
once `copilot.tenant` and `copilot.client_id` are set, belongs to the `web` capability, and a bio or a lineup card
allows it like any tool (`tools.allow: [copilot_ask]`). Not signed in, it answers one line saying so.

## Costs

A `cp:work` turn and a `copilot_ask` call add no dollars and mark the session's cost incomplete with the reason
"Copilot: billed by your tenant (credits or licence)". The TUI's status bar shows the priced part with its `+` (or the
token counts when nothing else is priced); `/cost` and Studio's Cost panel say the reason. Never `$0.00`.

## Troubleshooting

`halo doctor` has one Copilot row: not set up, signed in as whom until when, token expired, consent missing or billing
not enabled, each with its next step. Every failure of an ask is one line:

| The line starts | What happened | The next step |
|---|---|---|
| `Copilot: not set up` | `copilot.tenant` or `copilot.client_id` is unset | "Register the app" above |
| `Copilot: not signed in` | no refresh token in the env file | `halo copilot signin` |
| `Copilot: the sign-in has expired and the refresh failed (AADSTS70008 ...)` | the refresh token expired or was revoked | `halo copilot signin` |
| `Copilot: the tenant has not consented to <scopes>` | `AADSTS65001`, `invalid_scope`, or a 401/403 with a fresh token | an admin grants consent to those scopes |
| `Copilot: this account has no Microsoft 365 Copilot licence` | a 401/403 naming the licence (graph-beta) | an admin assigns a licence, or use `workiq` |
| `Copilot: Work IQ needs consumptive billing (Copilot Credits) enabled` | a 402, or an answer naming billing | an admin enables it, or use `graph-beta` |
| `Copilot: throttled (429) again after waiting N s` | Halo honoured `Retry-After` once and was throttled again | try again in a minute |
| `Copilot: offline mode: not connecting to <host>` | offline mode is on | `/offline off` |
| `Copilot: the redirect did not carry this sign-in's state` | a redirect from another sign-in reached the listener | sign in again |

What the mock server proves and a real tenant has not yet: the exact Work IQ scope name, where Work IQ puts its
citations and sensitivity label in an A2A answer (Halo reads `data` parts and metadata leniently), how Work IQ takes
file URLs (Halo names them in the turn's text) and web grounding (a metadata flag), and Graph's throttling (unpublished).
