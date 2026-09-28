# Automation is off

Turned off 2026-09-28 at the account owner's request: *"cancel GitHub
operations for flyer generator, no automation, it's driving up usage costs."*

Flyers are now **on demand only**.

```bash
python -m app.cli generate --no-upload   # render locally, look at them
python -m app.cli deliver                # put the good ones in Drive
```

## What was switched off

| | |
|:--|:--|
| launchd daily job on this Mac | booted out and the plist deleted |
| All six GitHub Actions workflows | `gh workflow disable` — repository level |
| Every automatic trigger in those files | commented out; only `workflow_dispatch` remains |
| `.github/dependabot.yml` | removed — it opened PRs weekly, and each PR re-ran Tests |

Two locks, deliberately. Disabling a workflow stops it even if a trigger comes
back; commenting the trigger stops it even if someone re-enables the workflow.

## One correction worth recording

GitHub Actions was almost certainly **not** the cost. This repository is
**public**, and Actions minutes are free on public repositories — the 30 runs
in September were billed at zero. If usage costs are climbing, the thing to
look at is Claude Code session usage, not CI.

Switching it all off is still a reasonable thing to want, and it is off.

## Turning any of it back on

Two steps, by design — one is not enough:

```bash
# 1. uncomment the trigger in the workflow file, then:
gh workflow enable generate-flyers.yml

# the local daily job:
./scripts/install-schedule.sh --yes-enable-automation
./scripts/install-schedule.sh --status     # check either way
```

## Checking nothing is running

```bash
launchctl list | grep flyer                # expect no output
gh workflow list --all                     # expect every row "disabled_manually"
crontab -l                                 # expect no crontab
```
