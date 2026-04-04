Process Twitter/X bookmarks into Obsidian vault notes.

Config: `config.yaml` in this directory (or override with `$ARGUMENTS` as a config path, or `T2O_CONFIG` env var).

## Quick reference

**Normal run** — reads `bookmarks.txt`, processes all new URLs, writes notes to vault:
```bash
bash scripts/process-bookmarks.sh [--config path/to/config.yaml]
# or:
./bookmark-to-obsidian process
```

**Skip enrichment** (faster, no Jina fetches for linked content):
```bash
bash scripts/process-bookmarks.sh --no-enrich
```

## What this command does

1. Reads `vault.path` + `vault.notes_folder` from config → vault root
2. Greps `source:` frontmatter from all vault notes to build a dedup set (normalized to x.com)
3. Reads `bookmarks.dir/bookmarks.file`, skips already-known URLs
4. For each new URL, fetches tweet data:
   - **Tier 1**: `https://api.fxtwitter.com/{user}/status/{id}` — full JSON, no auth
   - **Tier 2**: `https://r.jina.ai/https://x.com/{user}/status/{id}` — markdown fallback
   - **Tier 3**: Playwright DOM scrape — requires `npm install` + `cookies.json`
5. Classifies tweet into folder using `categories` keyword rules (first match wins, case-insensitive substring)
6. Writes `{vault_root}/{category}/{title}.md` with structured frontmatter + engagement stats
7. Optionally fetches linked URLs via Jina and appends as `## Linked Content`
8. Moves processed URLs to `bookmarks.processed_file`; removes them from bookmarks.txt

## Note structure produced

```markdown
---
tags: [type/tweet, source/twitter]
created: 2026-04-02
source: "https://x.com/username/status/1234567890"
author: "@username (Display Name)"
tweet_date: 2026-01-15
distillation: 0
---

# Note Title Here

**Source:** https://x.com/username/status/1234567890
**Author:** @username (Display Name) · Jan 15, 2026

💬 234 · 🔁 1.2K · ❤️ 8.9K · 👁 145.0K · 🔖 2.3K

## Summary

Full tweet text. [[Wikilinked]] entities auto-linked. Quote tweets and X Articles
get their own sections below.

## My Notes

-
```

## Key behaviors

**Dedup**: `source:` field is the identity. If a note with that URL already exists anywhere in vault_root, the URL is skipped — even if the file was renamed or moved within vault_root.

**URL normalization**: `twitter.com` and `x.com` are treated as identical. Vault notes saved with `twitter.com` sources correctly match incoming `x.com` bookmarks.

**Category matching**: case-insensitive substring. "model" matches "language model", "models", "multimodal". Earlier categories in config have priority.

**Wikilinks**: first occurrence of each entity only. Longest entities processed first (prevents "React" from matching inside "React Native"). Entities in quote tweet text are also linked.

**Title priority**: (1) `github.com/owner/repo` in tweet → `owner/repo`; (2) "Introducing/Launching X" → X; (3) cleaned first line; (4) "Tweet by @user"

**Distillation field**: starts at 0 (raw capture). User manually increments in Obsidian as they review/process the note. Never modified by this pipeline.

**Tier 2/3 notes**: No engagement line (stats unavailable). `tweet_date` set to today. No quote tweet or article sections.

**Failed URLs**: stay in `bookmarks.txt` for retry next run. Failures do not prevent other URLs from being processed.

**Idempotent**: safe to run multiple times. Duplicate protection works through `source:` frontmatter, not file existence.

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| "config.yaml not found" | No config yet | Run `./bookmark-to-obsidian setup` |
| Note already processed but re-processing | Source URL has wrong format or twitter.com/x.com mismatch | Check `source:` field in the note; run manually and watch dedup log |
| "All tiers failed" | Tweet deleted, account private, or FxTwitter/Jina down | Check URL manually; if deleted, remove from bookmarks.txt |
| Notes going to wrong folder | Category keyword not matching | Check tweet text vs keywords; add keyword to matching category in config.yaml |
| Enrichment slow | Many linked URLs, each taking 30s | Run with `--no-enrich` for speed; or reduce `enrichment.max_links_per_note` in config |
| Playwright (Tier 3) unavailable | npm packages not installed | Run `npm install` in project root; or run `./bookmark-to-obsidian cookies` |
