# Drop pictures here

Three folders, one job each. Drag files in, then run one command.

```bash
cd ~/Documents/Projects/flyer-generator
flyer intake
```

That reads all three folders, files everything into the right place, and tells
you what it did. Nothing is destroyed: files are moved, not deleted.

---

## 1 reference flyers

**Flyers you found that you want yours to look like.**

Competitor adverts, designs off Instagram, anything you like the look of. These
are studied for *style only* - layout, typography, colour, where the headline
sits. Their wording, logos and offers are never reused.

Screenshots are fine. HEIC is fine, it gets converted.

## 2 client photos

**Real photographs of real All Elite jobs, to put ON a flyer.**

Name them by job and stage and the system understands them without being told:

```
roof_bergenfield_before_001.jpg
roof_bergenfield_after_001.jpg
siding_cresskill_after_001.jpg
```

- The **service** word (roof, siding, gutters, windows) sets the category
- The **town** sets the project, which is how before/after pairs stay matched
  to the same house
- **before / during / after** sets the work state, which decides which
  messages the photo is allowed to illustrate

No name, no problem. It still imports, it just needs tagging afterwards.

## 3 drone media

**Straight off the SD card. Videos and stills together.**

Copy the whole `DCIM/101MEDIA` folder in here, or just plug the card in and run:

```bash
flyer ingest-media /Volumes/Untitled/DCIM/101MEDIA
```

Videos get watched, the best frame from each is scored and pulled out at full
resolution, and near-duplicates are thrown away. Stills are imported as they are.

---

## After importing

Nothing reaches a client flyer until you approve it:

```bash
flyer assets                    # what is waiting, best first
flyer assets --promote-top 10   # approve the best ten
flyer assets --unclassified     # anything still needing a work state
```

---

## Where everything else lives

| Folder | What it is |
| --- | --- |
| `app/` | the program itself. You never need to open this |
| `tests/` | proof the program works |
| `config/` | settings you can edit: campaigns, layouts, fonts, rules |
| `clients/` | each client's brand, logo and approved photos |
| `references/` | catalogued design references, once imported |
| `design-system/` | the permanent rules, so you never re-explain them |
| `output/` | scratch. Finished flyers go to Google Drive |
