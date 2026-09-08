# Setup

Three stages. The system is useful after stage 1 and fully automated after
stage 3.

---

## Stage 1 — Run it locally (no accounts needed)

```bash
git clone https://github.com/engineeringwithjp/flyer-generator.git
cd flyer-generator
./scripts/dev.sh install
./scripts/dev.sh preview
```

`./scripts/dev.sh install` creates a virtualenv, installs the package and downloads the
brand typefaces (Barlow Condensed and Lato, matching the All Elite website).

`./scripts/dev.sh preview` renders two flyers with no API key. Look in `output/`.

---

## Stage 2 — Turn on Claude

Get a key from [console.anthropic.com](https://console.anthropic.com).

```bash
cp .env.example .env
```

Set `ANTHROPIC_API_KEY` in `.env`, then:

```bash
flyer generate --count 2 --no-upload
```

`.env` is gitignored. It never gets committed.

### Cost

Roughly four Claude calls per flyer: campaign planning (once per batch),
copywriting, art direction, and a vision QA pass. Two flyers a weekday is about
40 runs a month. Reference analysis is a one-off per image and uses the cheaper
vision model. Set `ANTHROPIC_MODEL=claude-sonnet-5` to reduce it further.

---

## Stage 3 — Automate it

### 3a. Google Drive

Files land in your own Drive, owned by you. This needs an OAuth refresh token
rather than a service account, because a service account has no My Drive quota.

```bash
python scripts/google_oauth_setup.py --client-secrets ~/Downloads/client_secret.json
```

The script prints three values. Put them in `.env` locally, and in GitHub
Secrets for the automation.

Getting `client_secret.json`:

1. [console.cloud.google.com](https://console.cloud.google.com) → new project
2. APIs & Services → Library → enable **Google Drive API**
3. OAuth consent screen → External → add yourself as a test user
4. Credentials → Create credentials → OAuth client ID → **Desktop app**
5. Download the JSON

### 3b. GitHub Secrets

Repository → Settings → Secrets and variables → Actions:

| Secret | Required | What it is |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | yes | Claude API key |
| `GOOGLE_CLIENT_ID` | for Drive | From the OAuth setup script |
| `GOOGLE_CLIENT_SECRET` | for Drive | From the OAuth setup script |
| `GOOGLE_REFRESH_TOKEN` | for Drive | From the OAuth setup script |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | for Drive | The folder id from the Drive URL |

Optional repository **variables** (not secrets):

| Variable | Default |
| --- | --- |
| `ANTHROPIC_MODEL` | `claude-opus-5` |
| `ANTHROPIC_VISION_MODEL` | `claude-sonnet-5` |

Optional connector secrets, only if you want them:

| Secret | Enables |
| --- | --- |
| `UNSPLASH_ACCESS_KEY` | Supplemental stock photography |
| `FIGMA_ACCESS_TOKEN` + `FIGMA_FILE_KEY` | Master layout system |
| `CANVA_ACCESS_TOKEN` | Client-editable deliverables |

None of these are required. With all of them absent the system runs entirely on
internal sources, which is the intended default.

### 3c. Permissions

Settings → Actions → General → Workflow permissions → **Read and write**.
The daily job commits generation history back to the repository, which is how
the system remembers what it has already made.

### 3d. Check it

Actions → **Generate flyers** → Run workflow. Then wait for 10:07 tomorrow.

---

## What you still have to do by hand

| Thing | Why it cannot be automated |
| --- | --- |
| Add real client photography | Nobody has it but you |
| Verify the proof points in `client.json` | Only you can confirm they are true |
| Add a logo at `clients/all-elite/assets/logo/logo.png` | Same |
| Resolve the items in `design-system/CONFLICTS.md` | They are judgement calls |
| Drop reference flyers into `references/inbox/` | Taste is the input you provide |
