Read config.yaml from the project root to get vault path, folder routing rules, and wikilink entities. Default config location: ./config.yaml (override with T2O_CONFIG env var or $ARGUMENTS).

For each URL in the configured bookmarks file not already in the vault (check source: frontmatter via grep):
1. Extract username and tweet_id from the URL
2. Fetch https://api.fxtwitter.com/{username}/status/{tweet_id} via curl
3. Parse JSON for: text, author, date, engagement, media types, quote tweet, article content
4. Classify into folder using the categories defined in config.yaml (first keyword match wins, default_category as fallback)
5. Write vault note to {vault.path}/{vault.notes_folder}/{folder}/
6. If wikilinks are configured, wrap matching entities in [[double brackets]]

Alternatively, run the shell script directly:
```bash
bash scripts/process-bookmarks.sh [--config path/to/config.yaml]
```

## Note Template

```markdown
---
tags: [{base_tags from config}]
created: {today YYYY-MM-DD}
source: "{original x.com URL}"
author: "@{screen_name} ({display_name})"
tweet_date: {YYYY-MM-DD}
distillation: {distillation_start from config}
---

# {Title from first line of tweet}

**Source:** {url}
**Author:** @{screen_name} ({display_name}) · {Mon DD, YYYY}

💬 {replies} · 🔁 {retweets} · ❤️ {likes} · 👁 {views} · 🔖 {bookmarks}

## Summary

{Full tweet text}

## Quoted Tweet (if present)

> **@{quote_author}**: {quote text}

## Article Content (if X Article)

{article markdown extracted from blocks[]}

## My Notes

-
```

## Processing Rules

- Process in batches of config.processing.batch_size (default: 10)
- Log progress: [N/total] → folder/filename.md
- Skip URLs already in vault (matched via source: frontmatter)
- 404 / deleted tweets: log warning and skip
- When done, move processed URLs to configured processed_file
- Normalize twitter.com URLs to x.com
