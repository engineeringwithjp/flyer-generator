# Quality Control: The Human Design Test & Automated Gates

## 1. The Human Design Test (Mandatory Gate)
Before any flyer is delivered to the user or uploaded to Google Drive, it must pass the Human Design Test.

Ask: **"Does this look like it was designed by a high-end branding and marketing agency in New York / New Jersey, or does it look like an automated AI bot?"**

### Evaluation Checklist (100 Points Total)

| Check | Requirement | Points |
| :--- | :--- | :--- |
| **1. Architectural Realism** | Believable suburban architecture, realistic rooflines, correct window geometry. No AI melting or surreal turrets. | 15 |
| **2. Restraint & Negative Space** | The home has room to breathe. No walls of text or cluttered corner badges. | 15 |
| **3. Typography Execution** | High contrast, strong size contrast between hook and subhead, clean font pairing. | 15 |
| **4. Anti-AI Linguistic Check** | Zero em dashes (`—`), zero emojis, no buzzwords ("revolutionize", "elevate"). | 15 |
| **5. Brand Color Precision** | `#80272B` used selectively on CTA and badges; not smeared across the photo. | 10 |
| **6. Verified Claims** | No fabricated discounts, fake statistics, or unverified warranties. | 10 |
| **7. Mobile Feed Safe Margins** | Text and CTA are positioned within the safe zone (72px padding minimum). | 10 |
| **8. Hierarchy Clarity** | Viewer understands the core service and benefit within 1.5 seconds. | 10 |

**Passing Threshold**: Score >= **85/100**. Any score below 85 triggers automatic adjustment and regeneration.

---

## 2. Immediate Disqualification Criteria
If any of the following are detected, the flyer fails instantly:
1. Presence of any em dash (`—` or `--`).
2. Presence of emojis (`🔥`, `🚀`, etc.).
3. Fabricated discount numbers not in `client.json` (e.g. "$500 OFF").
4. Illegible dark text on dark backgrounds or white text on bright skies without a shadow/scrim.
5. Canvas dimensions not equal to 1080 x 1350 px.
