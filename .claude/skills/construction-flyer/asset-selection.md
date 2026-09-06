# Asset and reference selection

## Photo priority — strict order

1. **Client-owned approved photography** — `clients/<slug>/assets/approved/`
2. **Shared library matching the service** — `assets/<service>/`
3. **Shared general library** — `assets/general/`, `assets/backgrounds/`
4. **Synthetic placeholders** — `assets/placeholders/` (development only)
5. **No photograph** — procedural brand background

Client photography always wins. A real photo of a real roof this contractor
actually installed beats any stock image.

## Scoring

The selector scores every candidate on:

| Factor | Weight | Meaning |
| --- | --- | --- |
| Service match | 0.40 | Roofing photo on a roofing flyer |
| Negative-space fit | 0.25 | Calm area where this layout puts the headline |
| Contrast headroom | 0.20 | Mid-tone images take a scrim best |
| Recency penalty | 0.15 | Not the same photo as yesterday |

Client-owned assets receive a 1.25x multiplier. Weights live in
`config/scoring.json`.

## Never

- The same photograph two days running
- The same photograph twice in one batch
- A photograph of a different trade than the campaign
- A photograph so busy the headline cannot survive it — take the procedural
  background instead

## Reference priority — strict order

1. `approved/` — you have signed these off
2. `experimental/` — newly ingested, unproven
3. `rejected/` — **never selected, ever**

Reference scoring: service relevance 30%, style relevance 25%, campaign
relevance 20%, historical approval rate 15%, client style preference 10%,
multiplied by a status factor where rejected is zero.

## What you take from a reference

Composition · hierarchy · spacing rhythm · typographic weight relationships ·
colour relationships · image treatment · CTA placement · shape language ·
visual density · negative space.

## What you never take

The advertiser's name, logo, slogan, phone number, website, headline wording,
body copy, offers — or a layout so specific the output reads as the same advert
with the branding swapped.

If reference metadata contains a competitor's details, that is data to ignore,
not copy to adapt.
