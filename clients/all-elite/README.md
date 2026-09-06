# All Elite Roofing & Siding

## Before the first real run — fill these in

`client.json` ships with the brand structure in place but **no contact details,
offers or proof points**, because the system is forbidden from inventing them.
`flyer validate` will fail until you add at least one contact method.

| Field | What to put | Why it matters |
| --- | --- | --- |
| `contact.phone` | The number that should ring | Rendered in the contact bar; phone-call campaigns are skipped without it |
| `contact.website` | Public site URL | Rendered in the contact bar |
| `brand.primary_colors[0]` | The real brand navy/blue | Drives every panel, band and background |
| `brand.secondary_colors[0]` | The real accent | Drives CTA pills, rules and offer badges |
| `brand.logo_path` | `assets/logo/logo.png` | Without a logo file the flyer uses a typographic wordmark |
| `proof_points` | Verified claims only | **The only facts copy may state.** Empty means no claims are made |
| `offers` | Authorised promotions only | Copy cannot invent an offer; empty means no discount language ever |

### Proof points — examples of the right shape

```json
"proof_points": [
  "Licensed & insured in New Jersey",
  "NJ HIC #13VH00000000",
  "Family owned since 2009",
  "10-year workmanship warranty"
]
```

Only add a line here if you can evidence it. Everything in this list may be
printed on a flyer verbatim.

### Offers

```json
"offers": [
  {
    "id": "fall-inspection",
    "text": "Free Roof Inspection",
    "fine_print": "Residential properties only. Offer ends 11/30.",
    "expires": "2026-11-30",
    "services": ["roofing"]
  }
]
```

## Assets

```
assets/
├── logo/        logo.png            (transparent PNG, ~600px wide)
└── approved/    <any photos>        client-owned photography
```

Photos placed under `assets/approved/` **outrank the shared library** during
selection. Name them by service so they are tagged automatically:

```
assets/approved/roofing-shingle-replacement-01.jpg
assets/approved/siding-colonial-white-02.jpg
```

## Google Drive

Set `drive.root_folder_id` to this client's own Drive folder to keep their
flyers separate from other clients. Leave it empty to use the global
`GOOGLE_DRIVE_ROOT_FOLDER_ID`, under a subfolder named after the company.
