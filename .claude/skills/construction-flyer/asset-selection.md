# Asset Selection Rules: Photography & Graphic Sourcing

## 1. Asset Sourcing Hierarchy
To maintain authenticity and homeowner trust, assets must be selected strictly according to this priority ladder:

```
Tier 1: Client-Provided Project Photography (Highest Priority)
        ↓
Tier 2: Approved Internal Company Assets (Past All Elite projects)
        ↓
Tier 3: Approved Internal Background Library (Northeast architectural exteriors)
        ↓
Tier 4: Approved Historical Archive Images (Previously verified campaign photos)
        ↓
Tier 5: Unsplash (Commercial construction photography fallback ONLY when Tiers 1-4 lack a specific angle)
        ↓
Tier 6: Synthetic / AI Imagery (Forbidden for real property representations)
```

---

## 2. Hard Asset Selection Rules
1. **Never use stock photography when client project photography is available.** If All Elite has 15 completed roofing photos in `clients/all-elite/photos/`, the system MUST pull from those before querying Unsplash.
2. **Match Campaign to Asset Category**:
   - Roofing campaign -> Query `assets/roofing/` or client roofing photos.
   - Siding campaign -> Query `assets/siding/` or client siding photos.
   - Gutters campaign -> Query `assets/gutters/`.
3. **Negative Space Matching**:
   - Select photos with open sky when top headlines are planned.
   - Select photos with clean driveways or lower lawns when prominent bottom CTA banners are planned.
4. **Resolution Standards**:
   - Minimum asset resolution: 1080px wide. High-resolution originals are cropped and scaled to 1080x1350 with center-weighted aspect preservation.
