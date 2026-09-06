# Design rules

The structured, machine-readable version of these rules is
`design-system/principles/principles.json`, which is injected into your prompt
automatically. This document is the reasoning behind them.

## The hierarchy

```
PROPERTY / PHOTOGRAPHY
        v
PRIMARY HOOK          (L1 - one idea)
        v
SUPPORTING MESSAGE    (L2 - one sentence)
        v
KEY BENEFITS          (L3 - three or four maximum, often zero)
        v
BRAND / CTA           (L4)
```

This is the default, not a template. Product-education, before/after and
storm-emergency flyers legitimately reorder it. When you depart from it, say why
in `designer_notes`.

## Choosing the archetype

Pick the composition archetype first; the layout follows from it.

| Situation | Archetype | Layout |
| --- | --- | --- |
| Brand, premium positioning, full replacement | `hero-image` | `hero-full` |
| Standard service promotion (the workhorse) | `split-image` | `banner-lower-third` |
| Trust, licensing, credibility | `editorial-overlay` | `stat-stack` |
| Material quality, workmanship, close-up | `architectural-detail` | `hero-full` |
| Proof of work | `before-after` | `before-after` |
| Manufacturer product, assembly, insulation | `product-education` | `hero-full` |
| An authorised offer | `promotional` | `offer-badge` |
| Seasonal timing | `seasonal` | `split-diagonal` |
| Storm / emergency | `storm-emergency` | `offer-badge` |

## Overlay strength — the most common failure

Text placed over an under-darkened photograph is the single most frequent way a
flyer fails QA. Calibrate against the asset's reported `mean_luminance`:

| Photo | Overlay strength |
| --- | --- |
| Dark, calm (luminance < 0.35) | 0.35 – 0.50 |
| Mid-tone (0.35 – 0.6) | 0.50 – 0.65 |
| Bright, or busy (> 0.6) | 0.65 – 0.85 |
| Snow, bright sky, white siding | 0.75 – 0.90 |

When unsure, go darker. An over-darkened photo looks moody. An under-darkened
one looks broken.

## Contrast

- Body-scale text: minimum 4.5:1 against what is behind it.
- Display text: minimum 3:1.
- Never solve a contrast problem by shrinking the type. Solve it with a scrim,
  a solid band, or a different crop.

## Spacing

- Nothing important inside the safe margin.
- Space between groups must exceed space within a group. If the support line
  is as far from the headline as it is from the CTA, the grouping is broken.
- Empty space is a design decision. Do not fill it.

## Restraint

Before finalising, remove one element. If the flyer still works, leave it
removed. Over-design is the difference between an advert that looks bought and
one that looks generated.

## Variety obligations

Across one batch: different layout, different angle, different treatment.
Across a week: no repeated campaign, no repeated headline structure, no three
consecutive flyers with the same alignment.

Uniformity across 500 flyers a year is a worse outcome than any single
imperfect flyer.
