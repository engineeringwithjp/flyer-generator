# Put the real logo here

```
clients/all-elite/assets/logo/logo.png
```

**Requirements**

| | |
| --- | --- |
| Format | PNG with a **transparent** background |
| Width | 900–1600px (it is scaled down, never up) |
| Content | The full lockup: crown, roofline, ALL ELITE, ROOFING & SIDING |

A transparent background matters. The mark sits over dark photography, so a
white rectangle behind it will show as a white box.

If you only have a version on a white background, the flyers will still render:
the system falls back to a typographic wordmark until a usable file is here.

**A light version helps.** The mark is deep maroon on white, which has poor
contrast against dark photography. If you have (or can export) a white or
knocked-out version, add it as:

```
clients/all-elite/assets/logo/logo-light.png
```

and set `brand.logo_dark_path` in `client.json` to point at it. The renderer
picks whichever reads better against what is behind it.

After adding the file:

```bash
flyer validate     # confirms it is found
flyer generate --count 2
```
