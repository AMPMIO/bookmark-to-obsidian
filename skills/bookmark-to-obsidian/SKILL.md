---
name: bookmark-to-obsidian
description: Process Twitter/X bookmark URLs into structured Obsidian vault notes. Use when the user asks to process bookmarks, convert tweets to notes, sync bookmarks to vault, or run the bookmark-to-obsidian pipeline. Also use when asked to check vault for existing tweets or manage the bookmarks file.
---

You are running the bookmark-to-obsidian pipeline. Your job is to convert raw tweet URLs into structured, well-organized Obsidian notes that integrate with the user's existing knowledge graph.

Read all configuration from `config.yaml`. Reference files are in `skills/bookmark-to-obsidian/references/`.

---

## Quick Reference

**Minimal flow:** URL → fetch (3 tiers) → classify → generate note → write to vault.

**Example config → note frontmatter:**
```yaml
# config.yaml (excerpt)
vault:
  notes_folder: "Resources"
  default_category: "Inbox"
categories:
  - name: "AI Research"
    keywords: ["llm", "paper", "arxiv"]
    tags: ["topic/ai", "topic/research"]
template:
  base_tags: ["type/tweet", "source/twitter"]
```
Tweet text: *"New paper on LLM scaling from Anthropic..."*

→ Matched category: **AI Research** (keyword "llm" found)
→ Note saved to: `Resources/AI Research/New paper on LLM scaling.md`
→ Frontmatter:
```yaml
---
tags: [type/tweet, source/twitter, topic/ai, topic/research]
created: 2025-03-15
source: "https://x.com/AnthropicAI/status/..."
author: "@AnthropicAI (Anthropic)"
tweet_date: 2025-03-15
distillation: 0
---
```

**Key rules:**
- First matching category wins; categories checked in config order
- Wikilinks applied longest-entity-first to prevent partial matches
- Per-category `tags` merged with `base_tags` (no duplicates)
- `source:` field used for dedup on re-runs — don't change it

---

## Phase 1: Load Configuration

Read `config.yaml` (or path from `T2O_CONFIG` env var, or path in `$ARGUMENTS`).

Extract and validate:
```
vault_root        = vault.path + "/" + vault.notes_folder
default_category  = vault.default_category           (fallback: "Inbox")
bookmarks_file    = bookmarks.dir + "/" + bookmarks.file
processed_file    = bookmarks.dir + "/" + bookmarks.processed_file
batch_size        = processing.batch_size             (fallback: 10)
batch_delay       = processing.batch_delay_seconds    (fallback: 2)
categories        = categories[]                      (ordered list)
wikilinks         = wikilinks (dict or list)
enrichment_enabled = enrichment.enabled              (fallback: true)
max_links         = enrichment.max_links_per_note    (fallback: 3)
```

**Validation**: Fail immediately with a clear message if:
- `vault.path` is empty or the resolved path doesn't exist
- `categories` is not a list (or is absent — that's OK, uses default_category)
- Any category entry is missing a `name` field

---

## Phase 2: Build Known URLs (Dedup Set)

To avoid reprocessing, grep all `source:` fields from existing vault notes:

```bash
grep -rh "^source:" "{vault_root}/" 2>/dev/null \
  | sed "s/source: *[\"']*//;s/[\"']*$//" \
  | sed 's|twitter\.com|x.com|g' \
  | tr -d '[:space:]' \
  | sort -u
```

**Why normalization matters:** Older notes may have been saved with `twitter.com` URLs. New bookmarks arrive as `x.com` URLs. Always normalize both sides to `x.com` before comparing — do NOT skip this step.

---

## Phase 3: Filter Bookmarks

Read `bookmarks_file`, one URL per line. Skip:
- Empty lines
- Lines starting with `#` (comments)
- URLs already in the known-URL set (after normalizing both sides to x.com)

If nothing new remains, log "Nothing to process." and stop.

---

## Phase 4: Fetch Tweet Data (3-Tier Cascade)

For each new URL, extract `username` and `tweet_id`:
```
https://x.com/{username}/status/{tweet_id}
https://twitter.com/{username}/status/{tweet_id}
```

**Validate before fetching:** `tweet_id` must be all digits. If not, log a warning and skip.

### Tier 1 — FxTwitter API (preferred)
```
GET https://api.fxtwitter.com/{username}/status/{tweet_id}
```
- Timeout: 15 seconds
- **Success**: response is JSON AND contains a `tweet` key at root
- **Failure**: 404, non-JSON, JSON without `tweet` key, or empty response
- On failure: log "Tier 1 failed" and continue to Tier 2
- **Data available**: all fields — text, author (screen_name, display_name, followers), date, likes, retweets, replies, views, bookmarks, media, quote tweet, X Article

### Tier 2 — Jina Reader (fallback, no auth)
```
GET https://r.jina.ai/https://x.com/{username}/status/{tweet_id}
Headers: Accept: text/markdown, X-Return-Format: markdown
```
- Timeout: 30 seconds, 1 retry on network failure (not on application error)
- **Success**: non-empty markdown that does NOT start with "Error:"
- **Failure**: timeout, empty response, or "Error:" prefix
- On failure: log "Tier 2 failed" and continue to Tier 3
- **Data available**: tweet text only (no engagement stats, no structured metadata). Set `tweet_date` to today. Engagement line will be omitted regardless of config.

### Tier 3 — Playwright (DOM scrape, requires Node.js + cookies.json)
```bash
source lib/tier3-playwright.sh
tier3_fetch "$url" "$outfile" "$cookies_file"
```
- Only available if `node` is in PATH and `playwright` npm package is installed
- **Success**: JSON written to outfile containing `tweet.text` and `tweet.author`
- **Failure**: node not found, playwright not installed, DOM selector not found, or timeout
- On failure: log "All tiers failed: {url}" and **skip this URL** (add to failed count, do NOT add to processed file)
- **Data available**: tweet text, username from URL, display name from DOM (may fail if DOM changes). No engagement stats.

**Tier data availability summary:**
| Field | Tier 1 | Tier 2 | Tier 3 |
|-------|--------|--------|--------|
| Tweet text | ✓ | ✓ | ✓ |
| Author display name | ✓ | ✗ | ✓ (if DOM works) |
| Date | ✓ | ✗ (today) | ✗ (today) |
| Engagement stats | ✓ | ✗ | ✗ |
| Quote tweet | ✓ | ✗ | ✗ |
| X Article content | ✓ | ✗ | ✗ |
| Linked URLs (enrichment) | ✓ | ✓ | ✓ |

---

## Phase 5: Classify Tweet

Check tweet text (case-insensitive, substring match) against each category's keywords in config order. First match wins. Use `default_category` if nothing matches.

```python
text_lower = tweet_text.lower()
folder = default_category
for category in categories:
    for keyword in category["keywords"]:
        if keyword.lower() in text_lower:
            folder = category["name"]
            break  # stop checking keywords for this category
    else:
        continue  # no keyword matched, try next category
    break  # category matched, stop checking categories
```

**Edge cases:**
- Keywords are substring matches: "model" matches "language model", "models", "multimodal"
- Matching IS case-insensitive on both sides
- Category order in config determines priority — earlier categories win ties
- If `categories` is empty, all tweets go to `default_category`
- Category names become folder names: characters invalid in filenames (`/ \ : * ? " < > |`) should be avoided in category names

### Per-category tags

Each category definition may include an optional `tags` list. When a category matches, its tags are merged into the note frontmatter alongside `template.base_tags`:

```python
folder, category_tags = classify_tweet(text, categories, default_category)
all_tags = base_tags + [t for t in category_tags if t not in base_tags]
```

**Concrete example:**
```yaml
categories:
  - name: "AI Research"
    keywords: ["llm", "paper"]
    tags: ["topic/ai", "topic/research"]
template:
  base_tags: ["type/tweet", "source/twitter"]
```
Tweet: *"New paper on LLM scaling..."*
→ Matches: **AI Research** (keyword "llm")
→ Frontmatter: `tags: [type/tweet, source/twitter, topic/ai, topic/research]`

If no category matches, category_tags is `[]` — all_tags equals base_tags. If a category has no `tags` field, treat it as `[]` — no extra tags added.

---

## Phase 6: Generate Note

### Title extraction (priority order)

1. **GitHub repo**: if tweet text contains `github.com/owner/repo`, use `owner/repo` as title
2. **Announcement**: if text starts with "Introducing/Announcing/Launching/Releasing [X]", extract X (up to first punctuation or 80 chars)
3. **Cleaned first line**: first line of tweet, URLs removed, leading @mentions removed, truncated to 80 chars
4. **Fallback**: `"Tweet by @{screen_name}"`

Strip trailing punctuation from all extracted titles. If result is 3 chars or fewer after stripping, use fallback.

### Wikilink application

Config supports two formats:
```yaml
# Dict format: entity → target link
wikilinks:
  "React": "[[React Notes]]"
# List format: entity only (auto-wraps in [[entity]])
wikilinks:
  - entity: "React"
    target: "[[React Notes]]"  # optional, defaults to [[React]]
```

Apply to tweet text (and quote tweet text) — wrap each configured entity in its target link, **first occurrence only** per entity. Use word-boundary regex matching (`\bentity\b`) so "React" doesn't match "ReactNative". Process entities longest-first to prevent partial matches when entity names overlap (e.g., process "React Native" before "React").

### Note structure

See `references/note-template.md` for the exact format. Key rules:
- `source:` field must be the normalized `x.com` URL — this is used for dedup detection on future runs
- `distillation: 0` marks the note as raw/unprocessed in the user's knowledge maturity system
- Omit engagement line entirely if Tier 2/3 was used (no stats available) OR if `include_engagement: false`
- Omit `## My Notes` section if `include_my_notes: false`
- Include `## Quoted Tweet` section only if tweet has a quote tweet (Tier 1 only)
- Include `## Article Content` section only if tweet is an X Article (Tier 1 only)

---

## Phase 7: Enrichment (if enabled)

After generating the note, extract linked URLs from the tweet text:
- Match `https?://\S+`, strip trailing punctuation (`.`, `,`, `!`, `?`, `)`, `]`, `"`, `'`)
- **Exclude**: twitter.com, x.com, and t.co (URL shortener) domains
- **Deduplicate**: skip if same URL appears twice in tweet

For up to `max_links_per_note` URLs:
```bash
curl -sf --max-time 30 -H "Accept: text/markdown" "https://r.jina.ai/{url}"
```

On success, append to the note:
```markdown
## Linked Content

### [https://example.com/article](https://example.com/article)

{first 60 lines of Jina Reader output}

```

If Jina fails for a linked URL: silently skip that URL (don't abort enrichment for remaining URLs).
If all enrichment fails: note is written without the section (normal — many tweets don't have fetchable links).

---

## Phase 8: Write Note to Vault

```
filepath = vault_root / category / sanitize(title) + ".md"
```

**Filename sanitization**: remove `/ \ : * ? " < > |`, collapse multiple spaces to one, truncate to 80 chars. Do NOT truncate mid-word if possible.

**Before writing**: check if file already exists. If it does, log warning "Already exists: {path}" and skip (the dedup check in Phase 2 handles most cases, but the title could collide with an existing note).

**Create parent directories** (`mkdir -p`) before writing. Check for errors.

---

## Phase 9: Log and Cleanup

**During processing**: log each note as `[{n}/{total}] -> {folder}/{filename}.md`

**After all URLs processed**:
1. Print summary: `Done. Processed: N, Failed: N, Skipped: N`
2. Append successfully processed URLs to `processed_file`
3. Remove processed URLs from `bookmarks_file` (rewrite file with unprocessed URLs only)
4. Note: failed URLs stay in `bookmarks_file` for retry on next run

**Batch delay**: after every `batch_size` URLs (not failures), pause `batch_delay` seconds.

---

## Obsidian Organization Principles

When choosing categories and wikilinks, optimize for Obsidian's graph view and Dataview queries:

**Category folders map to the graph's clusters.** Choose category names that match how you think, not just what keywords appeared. A tweet about "how Vercel deploys Next.js" is "Web Development" even if you also have "DevOps" — file by the topic you'd search for.

**The `source:` frontmatter field is load-bearing.** It must be an exact `x.com` URL. Dataview queries like `WHERE source != ""` identify all sourced notes. Do NOT put anything else on this line.

**Tags use hierarchical format** (`type/tweet`, `source/twitter`) for Obsidian's tag browser and Dataview filtering:
- `type/tweet` — distinguish from your own writing, MOC notes, etc.
- `source/twitter` — filter by origin platform

**Wikilinks create graph edges.** Only wikilink entities that have (or will have) pages in your vault. A wikilink to a non-existent page creates an orphan node — visible in graph view as a floating red dot. Configure wikilinks conservatively.

**Distillation field tracks note maturity** (inspired by evergreen/atomic note methodology):
- `0` — raw capture, no review
- `1` — reviewed, key points identified
- `2` — integrated into a longer note or MOC
- `3` — core idea extracted into permanent note

Users increase this manually in Obsidian. Do NOT modify it during processing.

**`## My Notes` is for the user's annotations.** Leave it with just `-` as placeholder. It must come last in the note so the user can write below without hitting frontmatter or structured sections.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| All 3 tiers fail | Log warning, skip URL, add to failed count. URL stays in bookmarks.txt for retry. |
| note-generator.py produces empty title or folder | Log warning, skip URL. |
| mkdir fails | Log warning with path, skip URL. |
| File write fails | Log warning, skip URL. |
| Enrichment URL fails | Log nothing, continue to next enrichment URL silently. |
| Config invalid | Print specific error (missing field, wrong type), exit immediately. |
| bookmarks.txt missing | Print error with path, exit. |
| vault_root doesn't exist | Print error — vault path in config.yaml may be wrong. |

**Processing is idempotent:** you can re-run at any time. Already-processed URLs are filtered by the `source:` dedup check. Running twice does not create duplicate notes.

**If processing crashes mid-run:** the processed URLs appended so far are in `processed_file`. The bookmarks.txt has not been cleaned yet (cleanup only runs at end). Re-run will re-attempt URLs that failed or weren't reached — safe.

---

## References

- `skills/bookmark-to-obsidian/references/note-template.md` — exact note format
- `skills/bookmark-to-obsidian/references/config-reference.md` — full config schema
