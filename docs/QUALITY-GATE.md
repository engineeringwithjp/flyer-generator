# The quality gate

> Every rule here exists because a flyer that broke it reached the client's
> Google Drive folder. None of them are hypothetical.

## Where flyers live before they are delivered

```
flyer generate --no-upload     ->  output/<date>/<client>/     (staging, local)
   ... you look at them ...
flyer deliver                  ->  Client Flyers/Flyers/...    (Google Drive)
```

Rendering never writes into Drive. It used to, and QA ran *after* the file was
written, so a flyer that failed its checks was reported as a failure and left
sitting in the client's folder anyway. Staging locally is what makes the gate
mean anything: holding a flyer back is recoverable, publishing a bad one is not.

`flyer generate` with delivery enabled does both halves in one pass. Use
`--no-upload` then `flyer deliver` when you want to see the batch first —
re-running `generate` picks *different* campaigns, so the flyers that reach the
client would not be the ones you looked at.

## What blocks delivery

| Check | Why it exists |
|---|---|
| `logo_on_every_flyer` | "From now on always put the logo" |
| `retired_company_name` | The business trades as All Elite Roofing & Siding |
| `no_before_photo_on_finished_message` | A worn roof under "completed work" |
| `before_after_pair_confirmed` | Two folders named `bergenfield` turned out to be two different houses |
| `service_matches_the_business` | A campaign for a trade the client does not offer |
| `copy_is_written_not_generic` | "What To Know About Gutters" |
| `renderer: … overlap by …` | The CTA button printed over the body copy in two layouts |
| `renderer: … does not read against …` | White type on a sunlit driveway |
| `duplicate_photo` (batch) | Four flyers, one photograph |
| `duplicate_headline` (batch) | — |

Warnings are recorded but do not block: an over-long word count, an eyebrow
that echoes the headline, a logo that had to be upscaled.

## What no automated check can see

Three things need a person, and the system is built to make that person's job
small rather than to pretend the job does not exist:

1. **Whether a before/after pair is really one house.** Matching project labels
   only prove two files were filed together. Set `pair_confirmed` on the spec
   once you have looked.
2. **Whether a photograph is safe to publish.** A worker at a roof edge with no
   visible harness is a legal and reputational problem that no pixel test finds.
   Put the reason in `provenance.hold_reason` and the asset stops being
   production-eligible.
3. **Whether the copy is any good.** The filler list catches templates. It does
   not catch a headline that is merely dull.

## Photography is the ceiling

Run `flyer coverage`. A campaign for a service with no photographs behind it
gets a generic exterior aerial, and the reader notices before they read a word.
Campaigns without coverage are listed in `campaigns_disabled` in the client
profile — remove one from that list as soon as the photographs exist.
