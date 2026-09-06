# Versioning and rollback

The point of this scheme: when a change makes the flyers worse, you can get back
to the version that was good, quickly, without reading a diff.

## Tags are the checkpoints

Every meaningful phase is tagged. `git tag -n` lists them with descriptions.

```bash
git tag -n                 # what checkpoints exist
git checkout v0.3.0        # look at that state
git checkout main          # come back
```

To actually revert `main` to a tag:

```bash
git checkout main
git revert --no-commit v0.4.0..HEAD
git commit -m "revert: back to v0.3.0 behaviour"
```

`git revert` is preferred over `git reset --hard` because the automation runs
from `main` and rewriting its history breaks anyone else's clone.

## Rolling back just one thing

Most regressions are configuration, not code, which makes them cheap to undo:

```bash
# The design system got worse
git checkout v0.3.0 -- design-system/principles/principles.json

# A layout regressed
git checkout v0.3.0 -- app/rendering/templates.py

# The copy rules got too strict
git checkout v0.3.0 -- .claude/skills/construction-flyer/copywriting-rules.md
```

Then `make preview`, look at the PNGs, and commit if it is better.

## Branch layout

```
main                    always deployable; the 10:07 job runs from it
feat/<thing>            new capability
fix/<thing>             a defect
design/<thing>          design-system or skill changes
references/ingest-N     opened by the ingest workflow
design-system/proposal-N  opened by the distillation workflow
```

## Version numbering

`vMAJOR.MINOR.PATCH`, where the meaning is about *output*, not API surface:

| Bump | Means |
| --- | --- |
| PATCH | A fix. Flyers look the same or slightly better |
| MINOR | New capability. Existing flyers still render the same way |
| MAJOR | Flyers will visibly change. Re-review the design system first |

## Cutting a release

```bash
./scripts/release.sh v0.4.0 "Connector decision engine"
git push origin v0.4.0
```

The script refuses to tag a dirty tree and runs `make check` first.

## Reproducing an old flyer exactly

Rendering is deterministic: the same `FlyerSpecification` always produces the
same pixels. Every flyer ships with its spec next to it (`flyer-01.json`), so
an old flyer can be re-rendered from that file even after the layout code has
moved on, by checking out the tag it was generated under.

Generation history (`data/generation-history/`) records the run id, campaign,
references, assets and QA score for every flyer ever produced, and is committed
by the daily workflow.
