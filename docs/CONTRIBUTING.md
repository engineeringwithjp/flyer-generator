# Contributing

Written for a small team, or for one person plus an agent, working on something
that runs unattended every weekday morning.

## Setup

```bash
./scripts/dev.sh install     # venv, dependencies, brand fonts
./scripts/dev.sh check       # ruff + pytest
./scripts/dev.sh preview     # render two flyers with no API key and no upload
```

## The rule that matters most

**The system may never invent a claim.** Statistics, discounts, warranties,
certifications, awards, years in business, customer counts and licence numbers
come from `clients/<slug>/client.json` or they do not appear. A change that
weakens this is not merged, regardless of how much better the copy reads.

## Where things live

| You want to change | Edit |
| --- | --- |
| What good design means | `design-system/principles/principles.json` |
| What the system must never do | `design-system/failures/failed-patterns.json` |
| How Claude is instructed | `.claude/skills/construction-flyer/*.md` |
| Which campaigns exist | `config/campaigns.json` |
| How references are scored | `config/scoring.json` |
| Which layouts exist | `config/layouts.json` + `app/rendering/templates.py` |
| Type pairings | `config/typography.json` |
| Connector behaviour | `config/connectors.json` + `app/connectors/policy.py` |
| A client | `clients/<slug>/client.json` |

Most changes are configuration. If you are editing Python to change a design
preference, you are probably editing the wrong file.

## Adding a layout

1. Add an entry to `config/layouts.json`.
2. Add a builder to `app/rendering/templates.py` and register it in
   `LAYOUT_BUILDERS`.
3. Add it to a composition archetype in `principles.json`.
4. `test_config_and_code_agree_on_the_layout_set` will fail until config and
   code match, and the parametrised render tests will cover it automatically.

Compose from the components on `FlyerRenderer`. Do not draw raw pixels in a
layout: shared margins, contrast handling and text fitting are the reason every
flyer looks like it came from the same studio.

## Commits

Conventional Commits, because the history is a rollback tool.

```
feat(renderer): add the stat-stack layout
fix(qa): stop flagging "Free Roof Inspection" as a risky claim
chore(deps): bump pillow
docs(readme): document the connector decision engine
```

Scopes in use: `renderer`, `qa`, `planner`, `copywriter`, `director`,
`references`, `assets`, `clients`, `drive`, `connectors`, `design-system`,
`cli`, `ci`, `docs`, `history`.

## Branches

`main` is always deployable: the 10:07 job runs from it.

```
feat/<thing>       new capability
fix/<thing>        a defect
design/<thing>     design-system or skill changes
references/<...>   catalogued references (usually opened by the bot)
```

See [docs/VERSIONING.md](VERSIONING.md) for the tagging scheme and how to
roll back.

## Before you open a PR

```bash
./scripts/dev.sh check          # ruff + pytest
mypy app
flyer validate
./scripts/dev.sh preview        # and look at the PNGs
```

A rendering change needs a before/after image in the PR. Numbers do not tell
you whether a flyer reads.

## Tests

`pytest` runs against a temporary repository root (`FLYER_ROOT`), so nothing
touches your real libraries. A guard fixture fails any test that opens a
socket: mock the service, or mark the test `@pytest.mark.integration`.

Every bug fix gets a regression test. Several tests in this suite exist because
a real defect got through: the dotted-parent-directory asset bug, the
"Free Roof Inspection" false positive, the logo colliding with the CTA.
