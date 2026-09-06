# Photography rules

## The house is the hero

When a real property photograph is supplied it is the dominant visual element.
Everything else — type, scrim, badge, logo — serves it.

The exceptions, and they are the only ones:

- `product-education` — a material detail or cutaway leads
- `before-after` — two panels share the weight
- `storm-emergency` — urgency may lead if the photograph is weak

## Preserve the property

When a real property photo is used, **preserve**:

architecture · roofline · window placement and proportion · overall proportions ·
landscaping · driveway · perspective · realistic construction detail

You adapt a photograph by **cropping, scaling and scrimming**. You never adapt
it by redesigning the house.

## What good looks like

- Photorealistic, professional real-estate photography
- Believable Northeast US / New Jersey suburban architecture
- Natural daylight; tasteful golden hour welcome
- Natural, maintained landscaping consistent with the neighbourhood
- Correct construction detail: plausible course spacing, real flashing,
  gutters that attach to something

## What fails

- Exaggerated mansions and fantasy architecture
- Impossible roof geometry — intersecting planes that cannot drain
- Unrealistic landscaping
- Excessive HDR, halo artefacts, artificial studio lighting on an exterior
- Architectural distortion from over-aggressive lens correction
- Anything that reads as AI-generated architecture

A homeowner in Bergen County can tell instantly whether a house is real. A fake
house destroys the credibility the rest of the flyer is trying to build.

## Choosing where the text goes

Read the asset's `clear_regions`. Put the headline where the photograph is
calm. If nothing is calm, use a layout with a solid band
(`banner-lower-third`) rather than fighting the image.

## When there is no photograph

The renderer draws a brand-coloured procedural background. This is a
first-class outcome, not a placeholder — a clean brand gradient with restrained
type reads as intentional design.

A procedural background always beats a mismatched photograph. A kitchen on a
roofing flyer is worse than no photograph at all.

## Video frames

Most of All Elite's real media is 4K drone *video*, not stills. Frames are
extracted by `flyer ingest-media`, scored for flyer suitability, and filed as
`client_frame`.

A frame is chosen on five measures, calibrated against this client's own
footage: sharpness (rejects motion blur), exposure, contrast, whether there is
a calm band for the headline, and detail balance (rejects frames that are
almost all sky or almost all roof). Near-duplicates are rejected by perceptual
hash, because a hovering drone produces many samples of the same shot.

An extracted frame is **real media but unapproved**. It ranks above stock and
below a curated client photograph, and it cannot reach a flyer until a human
promotes it. Treat a 4K frame as equal in quality to a still: at 3840x2160 it
comfortably exceeds the 1080x1350 canvas even after a 4:5 crop.

## Asset tiers, in strict order

```
client_photo    100   curated, approved project photography
client_drone     95   real drone stills
client_frame     90   frames extracted from real client video
internal         70   approved generic company photography
stock            45   licensed stock, gap-filling only
generated         5   never production
placeholder       0   never production
```

Anything whose origin cannot be established stays `unknown` and is barred.

## Placeholder assets

Files under `assets/placeholders/` are synthetic. They exist so the pipeline can
be exercised before real photography arrives. They are ranked below every real
asset and should be replaced as soon as client photography exists.
