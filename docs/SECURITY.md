# Security and privacy

## Reporting

Email the maintainer rather than opening a public issue. Do not include
credentials in the report.

## What must never enter this repository

- `ANTHROPIC_API_KEY`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`
- Service-account JSON keys
- Connector tokens (`UNSPLASH_ACCESS_KEY`, `FIGMA_ACCESS_TOKEN`, `CANVA_ACCESS_TOKEN`)
- Client contracts, pricing, customer lists or any personal data

`.gitignore` covers `.env`, `*credentials*.json`, `*service-account*.json` and
`token.json`. That is a safety net, not the control: do not create secrets in
tracked paths in the first place.

If a secret is committed, rotate it first and rewrite history second. Assume
anything pushed to GitHub is compromised the moment it lands.

## How secrets are handled

| Where | Mechanism |
| --- | --- |
| Local | `.env`, gitignored, loaded by `python-dotenv` |
| GitHub Actions | Repository secrets, injected as environment variables |
| Logs | `app/logging_setup.py` redacts `sk-ant-…`, `ya29.…`, `1//…` and PEM blocks before anything reaches a sink |
| Flyers | Only fields from `client.json` are rendered. Credentials are never in scope |

`Settings.describe()` is the only summary that gets logged, and it reports
booleans rather than values.

## Privacy assumptions

- **Client photography is commercially sensitive.** It lives in the repository
  under `clients/<slug>/assets/`, so the repository should be **private** if it
  holds real client photographs.
- **Reference images are third-party adverts.** They are stored for design
  analysis. The system is explicitly built not to reproduce them: see
  `.claude/skills/construction-flyer/reference-analysis.md`.
- **Generated flyers are gitignored.** Google Drive is the archive; CI artifacts
  expire after 30 days.
- **The GitHub Pages gallery is public if Pages is public.** Do not enable it on
  a repository containing client photography unless you intend that.
- **Images sent to Claude** are the reference being analysed and the flyer being
  reviewed. Nothing else leaves the machine.
- **Connectors are opt-in.** With no tokens configured, no external service is
  contacted at all. `flyer connectors` shows exactly what is reachable.

## Dependency hygiene

Dependabot runs weekly for pip and monthly for Actions. Runtime dependencies are
kept deliberately small: `anthropic`, `pydantic`, `Pillow`, `python-dotenv`, plus
the optional Google client libraries.
