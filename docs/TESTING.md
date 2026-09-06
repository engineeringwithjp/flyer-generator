# How to check the system actually works

Four levels, cheapest first. You can do all of them in about ten minutes with
no API key and no Google account.

---

## Level 1 — Does it run at all? (30 seconds, no credentials)

```bash
make install
make preview
```

`make preview` sets `FLYER_OFFLINE=1`, which disables every Claude call and uses
the deterministic planner and copywriter. You should see two flyers written to
`output/<today>/all-elite/`.

**What good looks like**

```
1. PASS Protect What Matters Most
   home-protection / hero-full
2. PASS What To Know About Siding
   siding-energy / stat-stack
```

Open the PNGs. They should be 1080x1350, on-brand, and readable. The copy will
be plain, because the offline writer is deliberately conservative: it is
forbidden from making any claim that is not in `client.json`.

**If it fails:** the error names the cause. `flyer validate` will tell you what
is misconfigured.

---

## Level 2 — Is every part sound? (20 seconds)

```bash
make check      # ruff + 260 tests
mypy app        # type checking
flyer validate  # configuration, clients, libraries, fonts
```

The test suite runs against a throwaway repository root, so it never touches
your real libraries, and a guard fixture fails any test that tries to open a
network socket.

**What the tests actually cover**

| Area | Examples |
| --- | --- |
| Config & clients | Bad JSON, mismatched slug, missing contact, adding a second client |
| Design system | Every rule classified, every archetype maps to a real layout, the NEVER list covers the stated failures |
| Assets | Corrupt images, service inference, client photos outranking stock, recency beating the client bonus |
| References | Rejected never selected, approved beats experimental, feedback moves the score |
| Rendering | All six layouts at four canvas sizes, determinism, text never overflows, overlay strength actually darkens |
| QA | Em dashes, emoji, AI filler, fabricated numbers, unauthorised offers, risky insurance claims, blank renders |
| Pipeline | Two flyers differ, consecutive days do not repeat, a render failure is reported not swallowed |
| Connectors | All eight scenarios from the integration brief, including every failure mode |
| Claude | Retries, tool-call enforcement, hallucinated asset ids rejected, fallback on error |
| Drive | Folder creation, duplicate detection, retries — all mocked |

---

## Level 3 — Does it look right? (2 minutes)

Numbers do not tell you whether a flyer reads. Render every layout and look:

```bash
for L in hero-full banner-lower-third split-diagonal offer-badge before-after stat-stack; do
  FLYER_OFFLINE=1 python - "$L" <<'PY'
import sys
from pathlib import Path
import app.ai.campaign_planner as cp, app.pipeline.generate as g
layout = sys.argv[1]; orig = cp.plan_campaigns
def patched(**kw):
    plan = orig(**kw)
    for f in plan.flyers: f.layout = layout
    return plan
g.plan_campaigns = patched
run = g.generate_flyers(count=1, upload=False, output_dir=Path("output/_layouts")/layout)
r = run.results[0]
print(f"{layout:22} {'PASS' if r.qa_passed else 'FAIL'} {r.qa_score}")
PY
done
open output/_layouts/*/flyer-01.png
```

**Check each one against the thumbnail test:** shrink it to about 180px wide.
Can you still read the headline? That is the single most important quality gate
and it is the one a machine judges worst.

Also look for: the logo colliding with anything, text against an edge, the
contact bar overlapping the CTA, an overlay too light for the photo behind it.

---

## Level 4 — Does it work with Claude and Drive? (needs credentials)

```bash
cp .env.example .env
# add ANTHROPIC_API_KEY
flyer generate --count 2 --no-upload
```

Compare against Level 1. The copy should be noticeably sharper and the art
direction more varied, because the planner, copywriter, design director and a
vision QA pass are all live.

Then reference ingestion:

```bash
cp ~/Downloads/some-flyer-you-like.jpg references/inbox/
flyer ingest-reference
flyer list-references
```

Then Drive:

```bash
python scripts/google_oauth_setup.py --client-secrets ~/Downloads/client_secret.json
# put the three printed values in .env
flyer generate --count 2
```

Check the Drive folder for `Flyers/2026/September/09-05/`.

---

## Testing the automation without waiting for 10:07

GitHub → Actions → **Generate flyers** → **Run workflow**. Same pipeline, same
code path; the only difference is that a scheduled run first asks
`flyer schedule-check` whether it is really 10:07 in New Jersey.

To check the schedule logic itself:

```bash
flyer schedule-check --tolerance 40   # exit 0 if now is the window
```

---

## Deliberately breaking it

Worth doing once, so you know what failure looks like:

```bash
# QA should reject an em dash
flyer generate --count 1 --no-upload --message "roofing — done right"

# QA should reject an invented claim
# (edit a proof point out of client.json, then generate a trust campaign)

# The renderer should fall back to a brand background
mv assets/placeholders /tmp/ && flyer generate --count 1 --no-upload

# Connectors should degrade rather than fail
flyer decide --no-asset --references 0
```

Every one of these should produce a clear message and a usable outcome, not a
stack trace.
