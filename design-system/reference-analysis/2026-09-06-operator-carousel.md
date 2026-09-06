# Reference analysis — operator-supplied professional flyers (2026-09-06)

Five flyers the operator supplied as "this is what professional looks like".
Analysed for design DNA only. No wording, logo, offer or trade dress from any of
these is reusable: three are competitors (Arruda Roofing, Abraham Roofing), one
is a manufacturer (IKO), one is an agency (FARM).

**The files are now in `references/inbox/`**, converted from the operator's HEIC
screenshots. Run `flyer ingest-reference` (needs `ANTHROPIC_API_KEY`) to have
them catalogued with ids and scored by the selector.

## The five

| # | Advertiser | Structure |
| --- | --- | --- |
| 1 | Arruda Roofing | Full-bleed drone roof. Giant two-tone headline. Accent pill sub-label. Row of four translucent process chips. Small contact line + logo at base |
| 2 | FARM (agency) | Full-bleed site photo. Logo integrated into the crane boom. One large soft headline mid-frame. One line at the base. Extremely minimal |
| 3 | Abraham Roofing | Aerial roof. Logo top-centre. Large headline, three-line support. Four accent pill labels with thin-line icons placed spatially over the roof. Accent pill CTA + phone at base |
| 4 | IKO (manufacturer) | Roof photo with an angled white panel cut across the lower third holding the logo. Headline top-left on sky. Very high white space |
| 5 | Abraham Roofing | Aerial roof. Headline with one word accented. Four white rounded cards, each a small photo + heading + two short lines. Solid accent CTA bar + phone |
| 6 | Harford Roofing | Full-bleed photo with **no scrim at all**. Enormous white geometric-sans headline over three staggered lines. Logo top-right. No chips, no CTA, no contact bar. A seasonal joke carries it |

## Addendum: the Harford flyer changes the picture

Reviewed later than the others, and it is the outlier worth learning from.

It has **none of the furniture**: no scrim, no chips, no CTA pill, no contact
strip, no accent colour. One photograph, one idea, three lines of white type.
It is the most confident piece in the set and the most "brand agency" of them.

That is a distinct archetype, not a variation of `hero-editorial`:

| | `hero-editorial` | `statement` |
| --- | --- | --- |
| Scrim | heavy, top and base | none, or barely any |
| Headline | condensed, tight, one accent word | large geometric sans, all white |
| Support | accent pill | none |
| Chips | yes | none |
| CTA | pill with phone | none |
| Logo | bottom-right, small | top corner |
| Best for | service promotion, the workhorse | seasonal, brand, a single joke or idea |

**It only works when the photograph can carry it.** A busy aerial would swallow
white type with no scrim. `statement` therefore requires an asset with a large
calm region, which the frame scorer already measures as `negative_space`.

Also worth noting: the headline lines are **horizontally staggered**, each
starting further right than the last. That is a deliberate device, not
centring.

## Shared DNA — this is the house style

**HARD observations** (present in 4 or 5 of 5):

1. **The photograph is the entire canvas.** Full-bleed, edge to edge. No layout
   crops the photo into a box or gives it less than the full frame.
2. **Real aerial / drone photography of an actual roof.** Not stock, not
   ground-level, not illustrated. Four of five are drone shots.
3. **Copy sits directly on the photograph**, held legible by a scrim or by
   landing on naturally calm sky, never on a large solid colour band.
4. **One massive condensed uppercase headline**, occupying 15-25% of the canvas
   height. It is the first and often only thing read.
5. **Exactly one word of the headline is in the accent colour.** This is the
   single most repeated device across the set (flyers 1, 3, 5).
6. **Rounded pill / chip shapes** carry secondary information: process steps,
   service names, the CTA. Never square boxes.
7. **The CTA and phone number sit together at the base**, in an accent pill or
   bar, at genuinely readable size.
8. **The logo is small** and either top-centre or bottom-right. It never
   competes with the headline.

**SOFT observations:**

- Thin-line architectural icons, used only where they replace a word (flyer 3)
- A short accent pill *above* the supporting row, acting as a lead-in (flyer 1)
- Subtle grain on the headline type (flyer 1)
- An angled panel rather than a straight band, when a panel is used at all (flyer 4)

## What this contradicts in our current system

| Our current behaviour | What the references do | Action |
| --- | --- | --- |
| `banner-lower-third` fills the bottom 48% with solid maroon | Photo stays full-bleed; copy sits on a scrim | Demote this layout; it is closest to the "huge banners" negative rule |
| Headlines are a single flat colour | One word in the accent colour | **Add two-tone headline support** |
| Secondary info is plain bullets with dot markers | Rounded pills and chips | **Add a chip row component** |
| Contact bar is a plain full-width strip | Accent pill holding CTA + phone together | **Add a combined CTA/phone pill** |
| No icon support | Thin-line icons used sparingly | Deferred; icons need an asset set |

## What we deliberately do NOT copy

- Arruda's and Abraham's headlines, offers, phone numbers, licence numbers, logos
- The specific four process steps ("INSPECTION / MATERIALS / INSTALLATION /
  LONG-TERM PERFORMANCE") — that is Arruda's messaging
- IKO's anniversary device
- Flyer 5's four-card weather grid is close to the "repetitive cards" negative
  rule. It works there because each card carries a distinct photo. Treated as an
  OPTIONAL technique for education campaigns only, not a house pattern.

## Note on claims

Three of the five make claims we could not make without evidence: "BBB
Accredited", a licence number, "75 Years". All Elite's equivalents are already
in `client.json` (`NJ HIC #13VH12314700`, `GAF Master Elite`, `25+ years`), so
the same credibility move is available honestly.
