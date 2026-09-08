# How to use this — start here

Written for someone who has never run a command before. If a step doesn't work,
the "If it goes wrong" box under it tells you what to do.

**What this program does:** it makes two Instagram/Facebook flyers for
All Elite Roofing & Siding every weekday morning, using real photos and video
from your own job sites, and puts them in Google Drive.

---

## Part 1 — Open the Terminal and get set up (once, ~10 minutes)

### Step 1. Open Terminal

Press `Cmd + Space`, type `Terminal`, press Enter. A window with text appears.
This is where you type commands.

### Step 2. Go to the project

Copy this line, paste it in, press Enter:

```bash
cd ~/Documents/Projects/flyer-generator
```

Nothing visible happens. That's correct — you've just moved into the folder.

### Step 3. Install it

```bash
./scripts/dev.sh install
```

This takes 2–3 minutes. It downloads the fonts and the code libraries. You'll
see a lot of scrolling text. Wait for your prompt (`$`) to come back.

> **If it goes wrong:** if you see `make: command not found`, run
> `xcode-select --install`, click through the installer, then try again.

### Step 4. Make your first flyers

```bash
./scripts/dev.sh preview
```

In about 5 seconds you'll see something like:

```
1. PASS  The Difference Is In The Details
   premium-roofing / hero-editorial
2. PASS  We Walk Every Roof We Sell
   roof-replacement / hero-full
```

**Open them:**

```bash
open output
```

Finder opens. Go into today's date folder, then `all-elite`. Double-click the
PNG files.

**You've now made flyers.** Everything below is about making them better.

---

## Part 2 — The five commands you'll actually use

Type these from inside the project folder (Step 2 above).

| What you want | Command |
| --- | --- |
| Make today's two flyers | `flyer generate` |
| Make one specific flyer | `flyer generate --count 1 --campaign siding --message "built-in insulation"` |
| Check everything is healthy | `flyer validate` |
| Pull photos off a drone card | `flyer ingest-media /Volumes/Untitled/DCIM/101MEDIA` |
| Approve photos for use | `flyer assets` |

That's genuinely it. The rest of this document explains the last two.

---

## Part 3 — Giving it your photos

The program will not put a fake photo on a real advert. Every image is labelled
with where it came from, and only **real, approved** photos can appear on a
flyer. There are three states:

```
   PLACEHOLDER          REAL, NOT REVIEWED          APPROVED
   fake, for testing    from your camera            you said yes
   never used           not used yet                used on flyers
```

### Pulling photos and video off a drone card

Plug in the SD card, then:

```bash
flyer ingest-media /Volumes/Untitled/DCIM/101MEDIA
```

It watches every video, picks the best-looking frame from each one, and saves
it. On your last card that was **135 videos → 132 usable frames** in about 12
minutes.

It picks frames the way a designer would: sharp (not blurry), well lit, and
with a calm patch of sky where the headline can sit. It also throws away
near-identical shots.

### Approving them

```bash
flyer assets
```

You'll see:

```
Asset library
  20 production-eligible
  186 real media awaiting review
  10 synthetic, permanently barred

Score   Source          Asset
  0.791 client_frame    ...dji_0085_frame_28s
  0.789 client_frame    ...dji_0003_frame_23s
```

Higher score = better flyer photo. To approve the best ten:

```bash
flyer assets --promote-top 10
```

To look at them first, open `clients/all-elite/assets/raw/frames` in Finder.

> **The important bit:** nothing you haven't approved will ever appear on a
> flyer sent to a homeowner.

### Adding photos from your phone or a folder

Drop them in here:

```
clients/all-elite/assets/approved/
```

Name them by job so the program understands them:

```
roof_bergenfield_before_001.jpg
roof_bergenfield_after_001.jpg
siding_cresskill_001.jpg
```

Then run `flyer catalog`. The `before`/`after` naming is what lets it build a
proper before-and-after flyer from **the same house** — never two different
ones.

---

## Part 4 — Teaching it what you like

When you see a flyer online that you'd want yours to look like, save the image
and drop it in:

```
references/inbox/
```

Then:

```bash
flyer ingest-reference
```

It studies the design — the layout, where the headline sits, how the photo is
treated — and files it. It does **not** copy the advert. It learns the recipe,
then cooks with your photos and your name.

If you like what it learned:

```bash
flyer promote ref_000001 approved
```

Approved references have the strongest influence on future flyers.

---

## Part 5 — What good looks like

The house style, taken from the professional flyers you supplied:

- **The photo fills the whole flyer.** No big colour panels covering it.
- **One huge headline**, 3–8 words, in capitals, running nearly edge to edge.
- **One word of it in red.** Just one.
- **A red pill** under the headline carrying the supporting line.
- **Small rounded labels** in a row for the proof points.
- **Phone number and website small, bottom-left**, with the company name opposite.

Red `#DC1F26` is the flyer accent. The maroon and gold from the website are
deliberately *not* used — a website palette makes a flyer look like a template.

**It will never invent a claim.** No discount, warranty, statistic or award
appears unless it's written in `clients/all-elite/client.json`. Right now it is
allowed to say only these:

- Licensed & insured New Jersey contractor
- NJ HIC #13VH12314700
- GAF Master Elite contractor
- 25+ years of experience
- 2,500+ customers served
- 50-year GAF Master Elite warranty available

To let it say something else, add it to that file. To stop it saying something,
remove it.

---

## Part 6 — Making it run by itself

Once it's on GitHub, it runs at **10:07 AM, Monday to Friday**, and puts two
flyers in your Google Drive "Client Flyers" folder.

You need to add three secrets on GitHub (Settings → Secrets and variables →
Actions). `docs/SETUP.md` walks through getting them.

To run it right now instead of waiting: GitHub → **Actions** → **Generate
flyers** → **Run workflow**.

Each morning it also opens an issue listing what it made. Reply on it:

```
approve run_2026-09-06_ab12cd_01
reject run_2026-09-06_ab12cd_02 too much text
```

It learns from that. Rejections make it less likely to repeat whatever caused
them.

---

## When something looks wrong

| What you see | Why | Fix |
| --- | --- | --- |
| Flyers have a plain colour background, no photo | No approved photos yet | `flyer assets --promote-top 10` |
| The writing is plain and generic | No Claude key, so it's using safe fallback words | Add `ANTHROPIC_API_KEY` to `.env` |
| Fonts look wrong | Fonts didn't download | `python scripts/fetch_fonts.py` |
| Nothing in Google Drive | Not connected yet | See `docs/SETUP.md` |
| A flyer says FAIL | It failed a quality check on purpose | Open the `.json` next to it; it lists why |
| `command not found: flyer` | Not in the project folder | `cd ~/Documents/Projects/flyer-generator` |

**Nothing that fails a quality check is ever uploaded.** A FAIL is the system
protecting the client, not a crash.

---

## Working on it again later

### Where the project actually lives

```
~/Documents/Projects/flyer-generator        <- the real project. This is it.
```

That folder is the git repository, and everything in it is pushed to GitHub.
Nothing else on your Mac is needed.

### About `.claude/worktrees/`

Claude Code sometimes makes a **worktree** — a scratch copy of a project — so it
can work without disturbing your files. They are disposable by design.

The one currently sitting in this project is stale: it is an older snapshot,
and it does not even belong to this repository (it belongs to a different repo
that happens to be checked out in your home folder). It is roughly 790 MB of
duplicate.

**Deleting it loses nothing.** To remove it cleanly, so git's bookkeeping stays
tidy:

```bash
git -C ~ worktree remove --force ~/Documents/Projects/flyer-generator/.claude/worktrees/flyer-generation-agent-35692d
git -C ~ worktree prune
```

If that reports an error, the blunt version is fine too:

```bash
rm -rf ~/Documents/Projects/flyer-generator/.claude/worktrees
git -C ~ worktree prune
```

### Getting revisions from Claude Code afterwards

Nothing changes. Open the project the way you normally would:

```bash
cd ~/Documents/Projects/flyer-generator
claude
```

Then ask for what you want — *"make the headline bigger"*, *"add a layout for
gutter guards"*, *"the red is too bright"*. Claude reads the project, makes the
change, and you commit it.

If Claude Code decides it wants a worktree for a particular job, it creates a
**fresh** one automatically and cleans it up afterwards. You never have to make
one yourself, and you never have to keep an old one around.

### If you ever do lose the folder

```bash
cd ~/Documents/Projects
git clone https://github.com/engineeringwithjp/flyer-generator.git
cd flyer-generator
./scripts/dev.sh install
flyer drive-setup --write
```

You would need to re-add two things that are deliberately not in git: your
`.env` (secrets) and `clients/all-elite/assets/raw/` (large unreviewed media).
Everything else — code, design system, approved photos, references, history —
comes back with the clone.

### Rolling back a change you dislike

```bash
git tag -n                  # the checkpoints
git checkout v0.6.0         # look at an older state
git checkout main           # come back
```

Or undo just one thing:

```bash
git checkout v0.6.0 -- design-system/principles/principles.json
```

---

## The one-line version

```bash
cd ~/Documents/Projects/flyer-generator && flyer generate
```

Two flyers. Real photos of real roofs you built. Every weekday.
