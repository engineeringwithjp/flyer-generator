# Reference Analysis: Visual Extraction & Inspiration

## 1. Reference vs. Asset Distinction
- **Reference**: Teaches the system **how to design** (layout balance, typography contrast, color harmony, visual rhythm). Never directly embedded in the client's flyer.
- **Asset**: The photograph, logo, or diagram **actually placed** inside the final rendered flyer.

---

## 2. Ingestion & Characteristic Extraction
When a new inspiration flyer is placed in `references/inbox/`, the intake pipeline extracts:
1. **Layout & Archetype**: Hero placement, split-screen, editorial grid, card overlay.
2. **Typography Structure**: Scale ratio between headline and subhead, font style (Modern Sans vs Classic Serif).
3. **Color Treatment**: Accent usage, gradient opacity, dark vs light theme.
4. **Information Density**: Low, medium, high.
5. **CTA Treatment**: Floating pill, full-width banner, minimal text link.
6. **Recommended Categories**: e.g., `["roofing", "siding", "emergency"]`.

---

## 3. The 3 Reference Tiers
- **Approved (`references/approved/`)**: Proven high-performing designs that define the agency's house style. High selection weighting (85-100).
- **Experimental (`references/experimental/`)**: Fresh concepts being tested for variety. Moderate selection weighting (50-70).
- **Rejected (`references/rejected/`)**: Designs with poor conversion, cluttered layouts, or AI artifacts. **Weight = 0** (never used for generation; analyzed strictly as anti-patterns).

---

## 4. Multi-Reference Blending
Instead of imitating a single flyer:
- Take **Composition** from Reference A (e.g. editorial sky headline).
- Take **CTA styling** from Reference B (e.g. crimson pill with white phone typography).
- Take **Badge hierarchy** from Reference C (e.g. semi-transparent glassmorphic benefits card).
- Combine with **Client Project Photography** to create a 100% original flyer.
