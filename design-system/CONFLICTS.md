# Conflict log

Contradictions between sources are recorded here and resolved explicitly rather
than silently. Anything marked **NEEDS YOUR CALL** should be confirmed.

---

## C-001 — Which maroon is the brand maroon? **NEEDS YOUR CALL**

| Source | Value |
| --- | --- |
| Operator specification (this project) | `#80272B` described as "the All Elite accent" |
| Live website `app/globals.css` (`--color-maroon`) | `#6B1528` |

**Resolution applied:** `#6B1528` is used as the primary brand colour, because
it is the value shipping on the live site and therefore what customers already
associate with the brand. `#80272B` is 6% lighter and warmer; the two are close
enough that a flyer using either reads as on-brand.

Change one line in `clients/all-elite/client.json` if you want the other:

```json
"primary_colors": ["#80272B", "#3D0C18", "#8F2A3C"]
```

---

## C-002 — What colour is the CTA? **NEEDS YOUR CALL**

The operator specification says the accent (`#80272B`) should drive CTAs,
accent words, rules and icons.

**Problem:** most All Elite layouts place the CTA on a maroon panel. A maroon
CTA on maroon is invisible, which violates the hard contrast rule.

**Resolution applied:** brand gold `#C9952A` (also from the live site) is the
functional accent — CTA pills, rules, badges, bullet markers. Maroon is the
primary surface colour. This keeps the *intent* of the rule ("the brand colour
punctuates, it does not flood") while satisfying the 4.5:1 contrast floor.

To force maroon CTAs instead, swap `secondary_colors[0]` to a maroon and the
renderer will pick contrasting ink automatically — but check the result.

---

## C-003 — Design-system file location

| Source | Location |
| --- | --- |
| Earlier instruction | `data/design-system/*.json` |
| Later instruction | `design-system/{principles,preferences,failures}/` |

**Resolution applied:** the later instruction wins. Canonical location is
`design-system/` at the repository root. `data/` holds only generated state
(indexes and generation history), which keeps hand-authored knowledge and
machine-written state cleanly separated.

---

## C-004 — Skill document set

The two specifications listed different file sets (one included
`construction-marketing.md`, the other did not but added `photography-rules.md`,
`branding-rules.md`, `reference-analysis.md` and `negative-rules.md`).

**Resolution applied:** the union. `construction-marketing.md` earns its place —
seasonality and trade-specific customer psychology are not covered by any other
document.

---

## C-005 — Manufacturer products

`ASCEND® Composite Foam-Backed Siding` and `CertainTeed® CertaPlank®` were named
in the operator specification but do **not** appear anywhere on the live
website. GAF Timberline HDZ and GAF Master Elite do.

**Resolution applied:** all three are recorded in `client.json` under `products`,
because the operator stated them directly. Their `benefits` lists are minimal and
contain only what was stated — no performance numbers were invented.

**NEEDS YOUR CALL:** confirm All Elite actually installs the two siding
products, and add any verified benefit claims you want copy to be allowed to use.

---

## C-006 — Proof points

None were supplied in the flyer specification. The six now in `client.json` were
read from All Elite's own live website (`25+ years`, `2,500+ customers`,
`GAF Master Elite`, `NJ HIC #13VH12314700`, `licensed & insured`, `50-year
warranty available`).

**NEEDS YOUR CALL:** these are the only claims the system is permitted to print.
Verify each one is still accurate before the first live run.

---

## C-007 — Company renamed; does the domain still match? **NEEDS YOUR CALL**

The operator confirmed on 2026-09-06 that the business has been through name
changes and the current trading name is **All Elite Roofing & Siding**.
`client.json` has been updated, and that name now appears on every flyer.

**Still unresolved:** `contact.website` is `alleliteconstructioncorpnj.com`,
which carries the *old* name. Two questions:

1. Is that domain still live and correct to print?
2. Is there a newer domain matching the new trading name?

This matters more than usual: contact details are reproduced byte-for-byte and
a wrong URL on 500 flyers a year is the one unrecoverable defect.

The licence number `NJ HIC #13VH12314700` and the GAF Master Elite credential
were read from the old site. Confirm both still apply to the renamed entity.

---

## C-008 — Flyers deliberately diverge from the website palette (RESOLVED)

Operator instruction, 2026-09-06: *"Do not look like the website."*

The live site is maroon (`#6B1528`) surfaces with gold (`#C9952A`) accents. That
is a website palette: it works on white, at desktop scale, with room to breathe.
Reproduced on a 1080x1350 flyer it produced large maroon bands and gold pills
that read as a corporate template rather than as marketing.

Every reference flyer the operator approved uses the same far simpler system:
**white type, one bright red accent, over dark photography.** No second accent,
no large colour panels.

**Applied:**

| Role | Was (website) | Now (flyer) |
| --- | --- | --- |
| Accent | `#C9952A` gold | `#DC1F26` red |
| Surfaces | `#6B1528` maroon | `#14181C` near-black |
| Type on image | white | white (unchanged) |

Maroon is retained as the third primary so it remains available for a client
who explicitly wants it, but it is no longer a default surface. Gold is gone
from flyers entirely.

The website itself is unchanged and the domain
`alleliteconstructioncorpnj.com` is confirmed correct to print (supersedes the
open question in C-007). The trading name on all future flyers is
**All Elite Roofing & Siding**.
