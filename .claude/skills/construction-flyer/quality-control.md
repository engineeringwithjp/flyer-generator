# Quality control

Two passes run on every flyer.

**Deterministic** (`app/pipeline/validate.py`) — no API, runs in CI, gates every
Drive upload. Dimensions, file integrity, placeholder text, duplicate words,
risky claims, unverified numbers, unauthorised offers, phone format, blank
output, edge bleed.

**Vision** (`app/ai/qa_agent.py`) — you, looking at the rendered PNG. The
judgement calls a machine cannot make.

A flyer fails when either pass records an `error`. On failure the pipeline
regenerates once with a heavier scrim and reduced copy, then keeps whichever
attempt scored higher.

## Your checklist, in priority order

### 1. The thumbnail test — highest weight
Imagine it 180px wide in a feed. Is the headline still legible? Is the message
still clear? If not, that is an **error**, not a warning.

### 2. Contrast
Any text sitting on a photo region too bright or too busy for it. **Error.**

### 3. Clipping and overlap
Text or logo running off an edge, colliding, or crowding the margin. **Error.**

### 4. Text volume
More than roughly 25 words. **Warning** at 25-34, **error** beyond.

### 5. Campaign relevance
Does the imagery match the service? A kitchen on a roofing flyer is an
**error**.

### 6. Photographic realism
Fake-looking architecture, impossible roof geometry, wrong construction detail.
**Error** — this destroys credibility.

### 7. Brand accuracy
Company name and contact details rendered correctly. A wrong phone number is
the only truly unrecoverable defect. **Error.**

### 8. Manufacturer subordination
Does a manufacturer brand dominate? **Error.**

### 9. The human design test

> Does this look like an actual professional designer created it?

Check: visual hierarchy · restraint · believable photography · intentional
spacing · typographic quality · coherent composition · appropriate branding ·
realistic architecture · the visual telling the story before the words.

Fail it if it resembles a generic AI advert, a Canva template, a corporate
infographic, a random AI poster, an over-symmetrical template, or an
over-designed advertisement. **Warning**, escalating to **error** when more than
one applies.

## Calibration

Be exacting, but do not invent problems. A plain, clean flyer that reads well at
thumbnail size is a **pass**, even if it is not exciting. Boring and legible
beats interesting and unreadable.

Mark `passed: false` only when at least one genuine `error` exists.

## The feedback loop

`flyer feedback <flyer_id> approve|reject --reason "..."` records the human
verdict. Approvals raise the score of the references used; rejections lower it.
Rejection reasons accumulate in the history and feed the next distillation.

Evidence priority: the client's own approved flyers > recorded preferences >
approved external references > experimental references.
