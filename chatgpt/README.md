# ChatGPT native flyer workflow

This folder is independent of the Antigravity/Nano Banana application. The image generation happens in ChatGPT's native image tool; `finish.py` only places the original logo and exact contact information onto finished artwork. It has no image API, credentials, network calls, or scheduler.

The first five posts were generated September 10, 2026 and uploaded September 11. All five were confirmed by refreshing the Google Drive destination. See `runs/2026-09-10.json` for the delivery record.

## Daily execution

Use `daily-prompt.md` in an environment with native image generation, access to the supplied logo/reference assets, source Drive read access, and output Drive create access. The requested cadence is 10:00 AM America/New_York daily. A saved prompt or this Python helper does **not** activate a schedule. Cloud scheduling and unattended Drive access must be configured separately before promising execution with the Mac asleep.

The supplied source root contains NEDA Technologies / Clients / All Elite Construction. Only read the relevant All Elite project assets. The output root is a different folder, Client Flyers. Do not change sharing or source files.

As of September 11, the inspected ChatGPT web account has no Google Drive plugin installed, and its cloud browser reports no saved cookies. Its default website permission is Always ask. No ChatGPT daily schedule has been activated: the cloud environment still needs authenticated source/output access and the actual logo/reference images, followed by a successful native-generation/upload run. A local desktop schedule would require this Mac and would not meet the requested asleep-Mac behavior. GitHub SSH access does not supply these capabilities.

## Optional original-logo finishing

Requires Pillow. For the included layout, native generation must leave the upper-right logo region and bottom contact region empty. The output is 1080 x 1350 with proportional scaling, never stretching. This helper is layout-specific; adapt reserved positions when creating a different composition.

```sh
python chatgpt/finish.py /temporary/batch.json \
  --logo /path/to/original/logo.png \
  --output /temporary/final
```

The manifest is a JSON list containing `name` (a JPG filename) and `generated_path` for each native tool output. Upload the resulting files, re-list Drive to confirm every filename, then remove temporary originals and finished copies. Keep source/reference assets. Do not keep generated image archives in this repository.
