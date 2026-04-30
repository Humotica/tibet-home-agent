# AInternet Home Agent

[![PyPI version](https://img.shields.io/pypi/v/tibet-home-agent.svg)](https://pypi.org/project/tibet-home-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**BYOK Mode 3 — relay your existing Claude / Gemini / ChatGPT subscription to your phone.**

Run this on your laptop. Pair it to your `.aint` sub-identity (e.g.
`home.vandemeent.aint`). Your phone's K/IT app sends prompts via I-Poll
to your home agent; the daemon dispatches to whatever upstream AI you
have configured locally and sends the answer back over I-Poll.

**No API key on your phone. Prompts never leave your hardware. The
phone trusts only the `.aint` you signed in with.**

## Why this exists

Three BYOK modes for K/IT / AInternet:

1. **API key on phone** — works today. You buy a Gemini / Anthropic / OpenAI key.
2. **Local model on LAN** — run Ollama or Gemma 4 on a Mac with unified RAM.
3. **Home agent relay (this package)** — reuse your existing desktop Claude /
   ChatGPT / Gemini Pro subscription. No new key, no new account.

Mode 3 is the cleanest for the millions of people who already pay for
a desktop AI app and don't want to pay twice.

## Quick start

```bash
pip install tibet-home-agent[gemini]   # or [anthropic] or [openai]
```

Set the environment variables:

```bash
export HOME_AGENT_AINT="home.vandemeent"            # your home-agent sub-domain
export HOME_AGENT_TOKEN="$(cat ~/.ainternet/.session.json | jq -r .token)"
export HOME_AGENT_PROVIDER="gemini"                  # or anthropic, openai, echo
export GEMINI_API_KEY="..."                          # the *daemon's* upstream key
export BRAIN_URL="https://brein.jaspervandemeent.nl"
```

Then run:

```bash
tibet-home-agent
```

You should see:

```
[home-agent] starting  aint=home.vandemeent.aint  brain=https://...  provider=gemini  poll=2s
```

On your phone (K/IT app): Settings → BYOK → provider = **Home agent**,
home-agent address = `home.vandemeent`. Send a chat. Watch the daemon
log show the dispatch + reply round-trip.

## How it works

1. Phone calls brain's `/api/kit/ask` with `provider=home_agent`,
   `api_key=home.vandemeent` (the home-agent address).
2. Brain pushes an I-Poll TASK to `home.vandemeent.aint` carrying the
   prompt + thread id.
3. This daemon polls inbox every 2 s, picks up the prompt, dispatches
   to the configured upstream (Gemini / Anthropic / OpenAI / echo),
   and pushes the answer back via I-Poll.
4. Brain matches reply by thread id, returns answer to phone.

The phone never sees the upstream key. The daemon never sees the
phone's user data beyond the prompt itself. Brain is a relay, not a
data store.

## Provider — `echo`

For first-run validation, set `HOME_AGENT_PROVIDER=echo`. The daemon
echoes back the user's last message prefixed with `[echo]`. Round-trip
should be < 5 s. Use this to confirm I-Poll plumbing works before
connecting a real provider.

## Roadmap

- v0.1 (this release) — Gemini / Anthropic / OpenAI / echo provider.
  Daemon needs its own upstream API key.
- v0.2 — MCP bridge: dispatch through a locally running Claude Desktop
  / ChatGPT app via MCP, so users with existing subscriptions don't
  need a separate API key.
- v0.3 — local model dispatcher (Ollama, llama.cpp) so privacy users
  can stay fully on-device.
- v0.4 — sealed-payload mode: prompts arrive encrypted, decrypted
  only on the user's device under user-side keys.

## License

MIT.
