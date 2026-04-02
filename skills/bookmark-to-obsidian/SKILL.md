---
name: bookmark-to-obsidian
description: Process Twitter/X bookmark URLs into structured Obsidian vault notes using the FxTwitter API. Use when the user asks to process bookmarks, convert tweets to notes, or run the bookmark-to-obsidian pipeline.
---

You are running the bookmark-to-obsidian pipeline. Read config.yaml from the project root for all configuration. See `skills/bookmark-to-obsidian/references/` for template and config details.

## Steps

1. **Load config** — Read config.yaml (or T2O_CONFIG env var path). Extract:
   - `vault.path` + `vault.notes_folder` → vault root for notes
   - `vault.default_category` → fallback folder
   - `bookmarks.dir` + `bookmarks.file` → input file
   - `categories[]` → folder routing rules
   - `wikilinks` → dict or list of entity → target mappings
   - `enrichment` → enabled flag + max_links_per_note
   - `template.*` → note formatting options

2. **Build known URLs** — Grep `source:` frontmatter from all vault notes to avoid duplicates:
   ```bash
   grep -rh "^source:" {vault_root}/ | sed "s/source: [\"']//;s/[\"']//"
   ```

3. **Filter** — Remove any bookmark URLs already in the vault.

4. **For each new URL (tiered fetch):**
   - **Tier 1 — FxTwitter:** `curl https://api.fxtwitter.com/{username}/status/{tweet_id}`
     - On success: use full structured JSON
     - On 404/error: fall through to Tier 2
   - **Tier 2 — Jina Reader:** `curl https://r.jina.ai/https://x.com/{username}/status/{tweet_id}`
     - On success: use markdown content (no engagement stats)
     - On failure: fall through to Tier 3
   - **Tier 3 — Playwright:** use `lib/tier3-playwright.sh` (requires Node.js + cookies.json)
     - On failure: log warning and skip URL

5. **Generate note** using `python3 lib/note-generator.py`:
   - Extract fields: text, author, date, likes, retweets, replies, views, bookmarks, media, quote, article
   - Classify into folder using config categories (first keyword match wins)
   - Apply wikilinks: wrap matched entity names in [[target]] (first occurrence only)
   - Smart title: GitHub repo > announcement pattern > cleaned first line > "Tweet by @user"

6. **Enrichment** (if `enrichment.enabled: true`):
   - Extract non-Twitter URLs from tweet text
   - Fetch up to `max_links_per_note` URLs via `https://r.jina.ai/{url}`
   - Append as `## Linked Content` section

7. **Write note** — Create `{vault_root}/{category}/{sanitized-title}.md`. See `references/note-template.md` for the exact format.

8. **Log** — Print `[N/total] -> folder/filename.md` for each note written.

9. **Cleanup** — Move processed URLs to `bookmarks-processed.txt`. Remove them from the input file.

## Rules

- Process in batches of `processing.batch_size`, pause `processing.batch_delay_seconds` between batches
- If `include_my_notes: false`, omit the My Notes section
- If `include_engagement: false`, omit the engagement line
- For quote tweets: add a `## Quoted Tweet` section with blockquote formatting
- For X Articles: add a `## Article Content` section with the article text blocks
- Sanitize filenames: remove `/ \ : * ? " < > |`, truncate to 80 chars
- Wikilinks: apply to tweet text, first occurrence of each entity only

## References

- `skills/bookmark-to-obsidian/references/note-template.md` — note format
- `skills/bookmark-to-obsidian/references/config-reference.md` — config schema
