# Historical prompts — the Prompt-to-Skill corpus

Drop your old flyer prompts here as plain `.md` or `.txt` files. One prompt per
file. Then run:

```bash
flyer distill
```

Claude reads the corpus, extracts the **underlying rules** (not the wording),
removes repetition, resolves contradictions, classifies each rule as
hard / soft / optional, and writes a **proposal** to
`design-system/proposals/`. Nothing is applied automatically — you review the
proposal and merge what you agree with.

```
historical-prompts/
├── successful/      prompts and briefs that produced flyers you liked
└── unsuccessful/    prompts that produced flyers you rejected
```

## Naming

Anything readable works. A useful convention:

```
successful/2026-03-siding-composite-insulation.md
unsuccessful/2026-04-roofing-too-much-text.md
```

## Optional front matter

If you add front matter, the distiller uses it to weight the analysis:

```markdown
---
outcome: successful
campaign: siding
what_worked: House stayed the hero; single benefit; type had room to breathe.
---

<the original prompt text>
```

For unsuccessful examples, `what_failed:` is the most valuable field you can
write — one honest line about what went wrong is worth more to the system than
the prompt itself.

## What the distiller will NOT do

- It will not invent a preference you never expressed.
- It will not promote a one-off instruction into a permanent rule.
- It will not silently pick a winner between two contradictory instructions —
  conflicts are reported with a proposed resolution and a reason.
