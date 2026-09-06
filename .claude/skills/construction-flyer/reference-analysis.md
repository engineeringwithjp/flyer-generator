# Reference analysis

When the operator drops a flyer into `references/inbox/`, you analyse it and
produce structured, abstract design metadata.

## What you are doing

Extracting **design DNA** for an original generator. You are not cataloguing an
advert for reproduction.

## Record

| Field | What to observe |
| --- | --- |
| `category` | Which trade the design serves |
| `style` | premium-modern, bold-promotional, clean-minimal, corporate-trust, urgent-emergency, warm-residential, industrial |
| `layout` | The layout family the design belongs to |
| `text_density` | low / medium / high |
| `visual_weight` | image-heavy / balanced / type-heavy |
| `cta_position` | Where the action sits |
| `image_treatment` | Overlay, duotone, cutout, vignette, wash |
| `typography` | The type system in the abstract: "condensed heavy display over light sans" |
| `color_characteristics` | Relationships: "dark neutral base, single warm accent" |
| `dominant_colors` | Up to 4 hex approximations of the palette |
| `composition_notes` | How the eye moves through it |
| `negative_space` | Where it breathes |
| `suggested_layouts` | Which of **our** layouts express this language |
| `recommended_campaigns` | Which of **our** campaigns it suits |

## Never record

The advertiser's company name, logo, slogan, phone number, website, address ·
the headline or body copy wording · any offer, price or discount shown ·
anything that would let someone recreate this specific advert.

If you find yourself transcribing the reference's words, stop. You have moved
from analysis to copying.

## Status on ingest

New references land in `experimental/`. Only the operator promotes to
`approved/`. Nothing is auto-approved.

## Reference-influenced rules are provisional

A pattern observed in one reference is inspiration for that flyer. It becomes a
permanent rule only when the operator explicitly approves it — via
`flyer distill` producing a proposal the operator merges, or by editing
`design-system/principles/principles.json` directly.

Never silently promote a one-off observation into a standing rule.
