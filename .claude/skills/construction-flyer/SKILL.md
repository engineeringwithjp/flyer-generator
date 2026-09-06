---
name: construction-flyer
description: Autonomous design, copywriting, asset selection, and rendering system for high-conversion residential construction marketing flyers (roofing, siding, gutters, windows, emergency repairs). Produces clean, editorial, human-crafted 1080x1350 flyers adhering to All Elite brand standards and anti-AI design principles.
---

# Construction Flyer Generation Skill

## 1. Overview & Objective
This skill transforms brief campaign prompts into production-grade, photorealistic 1080x1350 (4:5) social media flyers for residential contractors (defaulting to **All Elite Construction Corp.**). 

It enforces strict brand standards, preserves real architectural property photography, executes deterministic typography and layouts, applies rigorous quality assurance, and connects with Google Drive for daily distribution.

---

## 2. Core Execution Pipeline

When invoked with a campaign request (e.g. `Create today's All Elite flyer. Campaign: Composite siding. Focus: Built-in insulation.`):

```
┌─────────────────────────────────────────────────────────────┐
│ 1. LOAD CONTEXT                                             │
│    • Client Profile (clients/<client_id>/client.json)       │
│    • Generation History (output/history.json)               │
│    • Design System Rules (rules/*.md, data/design-system/)   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. CAMPAIGN & ANGLE PLANNING                                │
│    • Select service angle (avoid recent 7-day fatigue)      │
│    • Select layout archetype (Hero, Editorial, Cutaway, etc)│
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ASSET SELECTION                                          │
│    • Priority 1: Real client project photography            │
│    • Priority 2: Approved internal background library       │
│    • Priority 3: Connected Unsplash (stock fallback only)   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. REFERENCE BLENDING                                       │
│    • Extract layout/typography principles from references   │
│    • NEVER copy 3rd-party flyers pixel-for-pixel            │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. COPYWRITING SYNTHESIS                                    │
│    • Hook, subheadline, 3-4 benefits, CTA                   │
│    • Strict anti-claims check (no fake warranties/stats)    │
│    • Zero em dashes, zero AI emojis                         │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. DETERMINISTIC RENDERING                                  │
│    • Render 1080x1350 PNG with brand color #80272B accent   │
│    • Mobile safe margins, 2-second scanability              │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. QUALITY ASSURANCE (QA GATE)                              │
│    • Human Design Test score >= 85                          │
│    • Contrast, legibility, and architectural integrity      │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. ARCHIVE & CLOUD DELIVERY                                 │
│    • Record to output/history.json                          │
│    • Upload to Google Drive (folder: 12Ho15EiJumnZkSAPm...) │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Knowledge Base Routing

Detailed, non-duplicative knowledge is partitioned into specialized rulebooks:

| Rulebook | Path | Purpose |
| :--- | :--- | :--- |
| **Design Rules** | [`design-rules.md`](design-rules.md) | 14-level design hierarchy, composition archetypes, margins. |
| **Photography** | [`photography-rules.md`](photography-rules.md) | "House is the Hero", real-estate photorealism, architectural preservation. |
| **Copywriting** | [`copywriting-rules.md`](copywriting-rules.md) | High-impact copy, homeowner psychology, zero fabricated claims. |
| **Branding** | [`branding-rules.md`](branding-rules.md) | `#80272B` accent usage, logo placement, manufacturer subordination. |
| **Negative Rules** | [`negative-rules.md`](negative-rules.md) | Anti-AI blacklist: zero em dashes, zero emojis, no Canva clutter. |
| **Asset Selection** | [`asset-selection.md`](asset-selection.md) | Strict 5-tier photo sourcing priority ladder. |
| **Reference Analysis** | [`reference-analysis.md`](reference-analysis.md) | Abstracting inspiration from `references/inbox/`. |
| **Quality Control** | [`quality-control.md`](quality-control.md) | 10-point Human Design Test & automated scoring criteria. |

---

## 4. Machine-Readable Design System
The active parameters are stored in `data/design-system/`:
- `principles.json`: Canvas sizing (1080x1350), safe margins (72px), color palettes, font weights.
- `successful-patterns.json`: Validated hooks, CTA formulations, and proven compositions.
- `failed-patterns.json`: Documented visual anti-patterns flagged during human review.
- `preferences.json`: Dynamic learning weights adjusted by user approvals and rejections.

---

## 5. Daily Prompt Minimization Standard
When generating a flyer, you do **not** need to restate brand rules or layout requirements. Provide only:
```text
Client: All Elite
Campaign: Composite Siding
Focus: Built-in insulation
CTA: Free Estimate
```
All styling, architectural preservation, typography scale, negative constraints, and delivery pipelines are executed automatically.
