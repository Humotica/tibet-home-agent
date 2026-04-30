# tibet-home-agent — release status

Snapshot van waar de package vandaag staat qua publicatie en reach.

## Versie

`0.2.0` — alpha. Eerste publieke milestone na de v0.1 echo/gemini/anthropic/openai providers.

## Distributie

| Kanaal | Status | Datum | Naam | Notes |
|---|---|---|---|---|
| **GitHub** | live | 2026-04-30 | `jaspertvdm/tibet-home-agent` | public, MIT |
| **PyPI** | not yet | — | `tibet-home-agent` | geparkeerd; eerst uitkristalliseren werkend alle kanten |
| **App download (Companion+)** | not yet | — | bundled | toekomstige distributie-route voor mainstream gebruikers, naast PyPI voor devs |
| **Backup mirror** | live | 2026-04-30 | `/mnt/ohm-0/` | full mirror van /srv/jtel-stack |

## Wat werkt

- v0.2.0 daemon met providers: `echo`, `gemini`, `anthropic`, `openai`, `claude_cli`
- `claude_cli` mode = UPIP work-dir architecture: per-thread sandbox, blueprint.md, claude reads via Read-tool, harvest naar I-Poll
- Systemd integration: `tibet-home-agent.service` + `/etc/default/tibet-home-agent`, Restart=on-failure, boot-persistent
- End-to-end mobiel-test geslaagd via Pixel-app (Mode 3 BYOK home_agent)

## Op de roadmap

- v0.2.1 — stdin-passthrough mode voor `claude_cli` (3-5s i.p.v. 12-17s, voor casual chat)
- v0.3 — local model dispatcher (Ollama, llama.cpp)
- v0.4 — sealed-payload mode (TIBET-encrypted prompts decrypted alleen op user device)
- App-bundle distributie via Companion+ tier
- PyPI publish nadat v0.2.x stabiel is en distributie-besluit definitief

## Hoe gebruiken (na github clone)

```bash
git clone https://github.com/jaspertvdm/tibet-home-agent.git
cd tibet-home-agent
pip install -e .[anthropic]      # of [gemini], [openai]

export HOME_AGENT_AINT="home.yourname"
export HOME_AGENT_TOKEN="$(your aint session)"
export HOME_AGENT_PROVIDER="claude_cli"   # gebruikt lokale `claude` CLI, geen API key
export BRAIN_URL="https://brein.jaspervandemeent.nl"

tibet-home-agent
```

Voor permanent: gebruik `scripts/systemd/tibet-home-agent.service` als template.

## Hoort bij

Onderdeel van het TIBET ecosystem (zie `tibet`, `tibet-airlock`, `tibet-mux`, `tibet-hermes`). Geeft de mobiele app van een AInternet-gebruiker een veilige relay-bridge naar diens *eigen* desktop AI subscription.
