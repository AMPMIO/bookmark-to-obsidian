# Note Template Reference

The standard note format produced by bookmark-to-obsidian. Sections marked optional can be disabled in config.yaml.

## Template

```markdown
---
tags: [type/tweet, source/twitter]
created: YYYY-MM-DD
source: "https://x.com/username/status/1234567890"
author: "@username (Display Name)"
tweet_date: YYYY-MM-DD
distillation: 0
---

# Note Title

**Source:** https://x.com/username/status/1234567890
**Author:** @username (Display Name) · Mon DD, YYYY

💬 replies · 🔁 retweets · ❤️ likes · 👁 views · 🔖 bookmarks

## Summary

Tweet text goes here. [[Wikilinked]] entities appear in double brackets.

## Quoted Tweet  (only if tweet quotes another)

> **@quoteduser** (Quoted Display Name):
> Quoted tweet text
>
> Source: https://x.com/quoteduser/status/...

## Article Content  (only if tweet is an X Article)

Full article text extracted block by block.

## Linked Content  (only if enrichment is enabled and tweet contains URLs)

### [https://github.com/example/repo](https://github.com/example/repo)

Fetched markdown content from the linked URL (first 60 lines via Jina Reader).

## My Notes  (optional, controlled by include_my_notes)

-
```

## Frontmatter Fields

| Field | Description |
|-------|-------------|
| `tags` | From `template.base_tags` in config |
| `created` | Date note was created (today) |
| `source` | Original tweet URL (used for dedup detection) |
| `author` | `@screen_name (Display Name)` |
| `tweet_date` | Date tweet was posted |
| `distillation` | Starts at `template.distillation_start` (default 0) |

## Configuration Options

```yaml
template:
  base_tags: ["type/tweet", "source/twitter"]  # Tags for every note
  include_engagement: true   # Show the 💬🔁❤️👁🔖 line
  include_my_notes: true     # Add empty ## My Notes section
  distillation_start: 0      # Initial distillation frontmatter value

enrichment:
  enabled: true              # Fetch linked URLs via Jina Reader
  max_links_per_note: 3      # Max linked URLs to fetch
```

## Title Generation

Titles are extracted in priority order:

1. **GitHub repo pattern** — If tweet contains `github.com/owner/repo`, use `owner/repo` as title
2. **Announcement pattern** — If first line starts with "Introducing/Announcing/Launching", extract what follows
3. **Cleaned first line** — First line of tweet text, with URLs and @mentions removed
4. **Fallback** — `"Tweet by @username"`
