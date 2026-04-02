# bookmark-to-obsidian

Browser bookmarks to Obsidian vault notes. Topic classification, wikilinks, YAML frontmatter, folder routing. No API keys. Starting with Twitter/X, with GitHub, YouTube, and more coming.

## What it does

You bookmark things. They pile up. You never look at them again.

This pipeline pulls bookmarks out of your browser and writes them into your Obsidian vault as notes with metadata, topic tags, and cross-references.

```bash
./bookmark-to-obsidian
```

It scrolls your Twitter bookmarks, fetches each tweet, classifies it by topic, writes a note, and drops it in the right folder. Open Obsidian and your graph view has new nodes.

## How it works

```
Browser Bookmarks
    ↓
Playwright extracts URLs (or paste them manually)
    ↓
3-tier content fetching:
    Tier 1: FxTwitter API  (~200ms, free, structured JSON)
    Tier 2: Jina Reader    (~1-2s, fallback + linked content enrichment)
    Tier 3: Playwright     (~3-5s, authenticated, last resort)
    ↓
Topic classification → note template → wikilinks
    ↓
Obsidian vault (organized by folder)
```

### 3-tier extraction

Not every URL cooperates. The pipeline tries the fastest method first and falls back on failure.

**Tier 1: FxTwitter API.** Free, open, returns structured JSON for any public tweet. No auth, no rate limits, no cost. Handles 95% of tweets.

**Tier 2: Jina Reader.** Converts any URL to clean markdown. Steps in when FxTwitter fails (deleted tweets, outages). Also handles enrichment: when a tweet links to a GitHub repo or blog post, Jina fetches that content and appends it to the note.

**Tier 3: Playwright.** Headless browser with your saved session cookies. Two jobs: extracting bookmark URLs from your authenticated bookmarks page, and fetching tweets when Tiers 1 and 2 both fail. Slowest, but handles anything a browser can.

## Requirements

- Python 3.8+ and `curl` (pre-installed on macOS/Linux)
- Node.js 18+ (for Playwright bookmark extraction)
- An Obsidian vault
- A browser where you're logged into X/Twitter (for bookmark extraction)

Optional:
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) for LLM-assisted topic classification and title generation
- [Claude Desktop](https://claude.ai/download) with the included skill for chat-based processing

## Quick start

```bash
git clone https://github.com/ampmio/bookmark-to-obsidian
cd bookmark-to-obsidian
./setup.sh
```

Setup asks for your vault path, creates your config, and can export Chrome cookies for hands-free bookmark extraction.

### First run

**With cookies (hands-free):**
```bash
./bookmark-to-obsidian
```

**Without cookies (one manual step):**
```bash
./bookmark-to-obsidian extract    # copies JS to clipboard
# Paste in browser console at x.com/i/bookmarks
./bookmark-to-obsidian process    # processes extracted URLs
```

**With a URL list:**
```bash
./bookmark-to-obsidian process ~/urls.txt
```

### Commands

| Command | What it does |
|---|---|
| `./bookmark-to-obsidian` | Full pipeline: extract + process |
| `./bookmark-to-obsidian setup` | First-run configuration |
| `./bookmark-to-obsidian extract` | Pull bookmark URLs from Twitter |
| `./bookmark-to-obsidian process [file]` | Process URLs into vault notes |
| `./bookmark-to-obsidian cookies` | Export Chrome session cookies |

### Claude Code integration

```bash
cp .claude/commands/process-bookmarks.md ~/.claude/commands/
claude /process-bookmarks
```

Without Claude, the shell script classifies topics by keyword matching and uses the first line of a tweet as the title. With Claude Code, you get LLM-generated titles (repo names, tool names, topic summaries) and better folder routing. Both produce the same note format.

## Example output

A bookmarked tweet about a tool becomes:

```markdown
---
tags: [type/tweet, source/twitter, resource/ai-tools]
created: 2026-04-01
source: "https://x.com/someone/status/2038567965465944491"
author: "@someone (Some Person)"
tweet_date: 2026-03-30
distillation: 0
---

# TurboQuant: KV Cache Compression (Solo Dev vs Google)

**Source:** https://x.com/someone/status/2038567965465944491
**Author:** @someone · Mar 30, 2026
**GitHub:** https://github.com/user/turboquant

💬 118 · 🔁 510 · ❤️ 4.3K · 👁 549K · 🔖 4.4K

## Summary

Solo dev reverse-engineered Google's KV cache compression algorithm
using Claude in 7 days, then beat their benchmarks. 35B model running
on a MacBook with 4.6x compressed cache.

## Linked Content

> **github.com/user/turboquant** — Implements PolarQuant and QJL
> for near-lossless KV cache compression. Supports llama.cpp,
> MLX, and CUDA backends...

## My Notes

- Could reduce memory needs for [[My Project]]'s inference stack
- Compare with [[Quantization Notes]] for context on prior methods
```

Titles come from the content: tool names, repo names, "Introducing X" patterns. Not the raw first line of the tweet. The "Linked Content" section pulls in GitHub READMEs and blog posts found in the tweet via Jina Reader.

## Configuration

Everything lives in `config.yaml`. Only `vault.path` is required.

### Folder routing

Route notes to subfolders by keyword. First match wins.

```yaml
categories:
  - name: "AI Tools"
    keywords: ["open-source", "cli", "api", "github", "tool", "framework"]
  - name: "Web Dev"
    keywords: ["react", "nextjs", "typescript", "frontend", "tailwind"]
  - name: "AI Agents"
    keywords: ["agent", "multi-agent", "orchestration", "autonomous"]
```

No match sends the note to `vault.default_category` (defaults to `Inbox`).

### Wikilinks

Auto-link mentions of your vault pages in the "My Notes" section.

```yaml
wikilinks:
  "My Project": "[[My Project]]"
  "React": "[[React Notes]]"
  "Machine Learning": "[[ML Research|Machine Learning]]"
```

Leave this empty if you don't care about Obsidian's graph view. Notes work without it.

### Enrichment

When a tweet links to a GitHub repo, blog post, or docs page, the pipeline fetches that content via Jina Reader and appends it.

```yaml
enrichment:
  enabled: true
  max_links_per_note: 3
```

### Full reference

See [`config.example.yaml`](config.example.yaml) for every option, annotated.

## Supported content

| Type | Handling |
|---|---|
| Standard tweets | Full text, author, engagement, media type flags |
| Quote tweets | Quoted content as blockquote section |
| X Articles (long-form) | Full article body as markdown |
| Threads | Individual bookmarked tweet (thread unrolling planned) |
| Linked URLs | GitHub READMEs, blog posts fetched and appended |
| Protected/deleted | Skipped with a log warning |

## Comparison

| | bookmark-to-obsidian | Xquik API | twscrape | XActions |
|---|---|---|---|---|
| Cost | Free | $0.00015/call | Free | Free |
| Auth required | None (cookies optional) | API key | X cookies | X cookies |
| Obsidian integration | Built-in | No | No | No |
| Topic classification | Yes | No | No | No |
| Wikilinks | Configurable | No | No | No |
| Linked content enrichment | Yes (Jina) | No | No | No |
| Note templates | Yes | No | No | No |
| X Article extraction | Yes | Yes | No | No |
| Bookmark scraping | Yes (Playwright) | No | No | Yes |
| Multi-source (planned) | Yes | No | No | No |

Other scrapers stop at extraction. This one writes the notes.

## FAQ

**Do I need a Twitter/X API key?**
No. FxTwitter works with any public tweet, no authentication.

**Do I need to export cookies?**
Only for automated bookmark extraction. Without cookies, you paste a script in your browser console. Processing individual URLs needs no cookies at all.

**Private tweets?**
No. FxTwitter only sees public accounts.

**Custom note format?**
Template settings in `config.yaml` control tags, stats, and sections. For deeper changes, edit `lib/note-generator.py`.

**Works without Claude?**
Yes. The scripts run on Python and curl alone. Claude Code improves titles and classification but isn't a dependency.

**Rate limits?**
FxTwitter doesn't document any. The processor pauses every 10 tweets. 40+ per run works fine.

**Duplicates?**
Every URL is checked against your vault's frontmatter before processing. Already-saved tweets are skipped.

## Project structure

```
bookmark-to-obsidian/
├── bookmark-to-obsidian.sh           # Entry point
├── setup.sh                          # First-run config wizard
├── config.example.yaml               # Config template
├── package.json                      # Playwright
├── lib/
│   ├── config.sh                     # Bash config loader
│   ├── config.py                     # Python config loader
│   ├── note-generator.py             # Templates, classification, titles
│   ├── tier1-fxtwitter.sh            # FxTwitter API
│   ├── tier2-jina.sh                 # Jina Reader + enrichment
│   └── tier3-playwright.sh           # Playwright fallback
├── scripts/
│   ├── extract-bookmarks.js          # Playwright bookmark scroller
│   ├── extract-bookmarks-manual.js   # Browser console version
│   ├── extract-bookmarks-manual.sh   # Console version launcher
│   ├── process-bookmarks.sh          # Batch processor
│   └── export-cookies.sh             # Cookie export
├── .claude/
│   └── commands/
│       └── process-bookmarks.md
├── skills/
│   └── bookmark-to-obsidian/
│       └── SKILL.md
├── examples/
│   ├── config-minimal.yaml
│   ├── config-developer.yaml
│   ├── config-researcher.yaml
│   ├── config-news.yaml
│   └── sample-notes/
└── docs/
    └── adding-sources.md
```

## Roadmap

Classification, templates, and vault writing work with any input. New source = one extraction script.

### Done
- [x] Twitter/X bookmarks (Playwright + manual console)
- [x] Individual tweet URLs (paste and process)
- [x] 3-tier extraction (FxTwitter, Jina, Playwright)
- [x] Linked content enrichment (GitHub READMEs, blog posts)

### Planned
- [ ] GitHub starred repos
- [ ] YouTube watch-later
- [ ] Hacker News saved items
- [ ] Reddit saved posts
- [ ] RSS/Atom feeds
- [ ] Obsidian plugin (no CLI)
- [ ] Full thread unrolling
- [ ] Cron scheduling

## Contributing

PRs welcome. Where help matters most:

- **New sources.** Extraction scripts for GitHub stars, YouTube, HN, Reddit, RSS. See `docs/adding-sources.md`.
- **Classification.** The keyword matcher is basic. Better heuristics or an optional local model would help.
- **Example configs.** Your `config.yaml` for design, crypto, academics, DevOps, whatever.
- **Obsidian plugin.** Native plugin that removes the CLI dependency.

## License

MIT
