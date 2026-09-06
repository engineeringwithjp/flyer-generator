# Copywriting rules

## Structure

| Level | Field | Budget | Job |
| --- | --- | --- | --- |
| L1 | `headline` | 3-8 words, <= 54 chars | The whole message |
| L2 | `support` | one sentence, <= 110 chars | The specific, the local, the qualifier |
| L3 | `bullets` | 0-3, <= 44 chars each | Proof. Often correctly empty |
| L4 | `cta` | <= 32 chars | One action |
| — | `eyebrow` | <= 34 chars | Optional label: service, county, season |
| — | `offer_badge` | <= 26 chars | Only with an authorised offer |
| — | `disclaimer` | <= 120 chars | Offer fine print, verbatim |

Character budgets are hard renderer limits. The renderer will shrink type to
make an overlong headline fit, and small type fails the thumbnail test.

## Voice

Write for a homeowner on a phone who is not shopping for a roof.

- Plain language. If a contractor would not say it out loud, do not write it.
- Concrete over abstract. "Missing shingles after the last storm" beats
  "compromised roofing integrity".
- Benefit before feature. What they get, not what you do.
- Local specificity when true. "Bergen County homeowners" beats "homeowners".
- One idea. Two ideas is two flyers.

## The headline test

Read the headline alone. Does a stranger know what is being sold and why they
should care? If not, it is decoration, not a headline.

Then shrink it mentally to 180px wide. If it stops working, it is too long.

## Never invent

Discounts · statistics · percentages · warranties · certifications · awards ·
years in business · customer counts · licence numbers · guarantees · financing
terms · response times.

The only permitted sources are `client.proof_points`, `client.offers` and a
product's `benefits`. If a list is empty, the flyer makes no claim of that kind.

A number that is not traceable to the client profile is a QA error, not a
stylistic preference.

## Never write

- "Free roof", "no cost to you", "insurance will pay for everything"
- "Guaranteed approval", "we'll get your claim approved"
- Fabricated scarcity or countdowns
- "#1", "best", "top-rated" without a citable source in `proof_points`
- Storm urgency for a storm that did not happen

## Banned filler

unlock · elevate your · in today's · look no further · we've got you covered ·
game-changer · seamless · cutting-edge · world-class · unparalleled ·
take your home to the next level · peace of mind you deserve

These are the fingerprints of generated copy. Their presence is a warning; a
cluster of them is a failure.

## Density

Default is low. One hook, one supporting line, at most three or four benefits,
one CTA. Roughly 25 words total across the whole flyer.

Never say the same thing in two places. If the headline says "free estimate",
the CTA says something else, or the headline changes.

Never add text because space exists.

## CTAs that work

Get A Free Estimate · Book Your Free Inspection · Schedule Your Estimate ·
Call For Same-Day Service (only if the client offers it) · See Our Work ·
Request Your Quote

One CTA. Imperative. No full stop.
