# GitHub Open Source Build Plan: tweet-to-obsidian

## The Product

One command turns your Twitter bookmarks into an organized Obsidian knowledge base.

```bash
./tweet-to-obsidian
```

That's it. It opens your bookmarks, scrolls through them, fetches each tweet's content,
classifies it by topic, writes structured notes with metadata, and files them into the
right folders. When you open Obsidian, your graph view has new connected nodes.

## What Makes This Different

Every other Twitter scraper stops at extraction. Raw data, your problem to organize.
This one does the full loop: extract → fetch → classify → template → file → link.

No API keys. No paid services. No manual steps (once cookies are set up).

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  tweet-to-obsidian               │
│                                                  │
│  ┌──────────────┐    ┌────────────────────────┐  │
│  │   Extractor   │    │      Processor         │  │
│  │  (Playwright) │───▶│  Tier 1: FxTwitter     │  │
│  │              │    │  Tier 2: Jina Reader    │  │
│  │  Scrolls your│    │  Tier 3: Playwright     │  │
│  │  bookmarks   │    │                        │  │
│  └──────────────┘    │  ┌──────────────────┐  │  │
│                      │  │  Classifier      │  │  │
│  bookmarks.txt ─────▶│  │  (keyword match) │  │  │
│                      │  └──────────────────┘  │  │
│                      │  ┌──────────────────┐  │  │
│                      │  │  Note Writer     │  │  │
│                      │  │  (template +     │  │  │
│                      │  │   wikilinks)     │  │  │
│                      │  └──────────────────┘  │  │
│                      └───────────┬────────────┘  │
│                                  │               │
│                                  ▼               │
│                          Obsidian Vault          │
│                     (organized by folder)        │
└─────────────────────────────────────────────────┘
```

## Repo Structure

```
tweet-to-obsidian/
├── tweet-to-obsidian.sh              # Main entry point — one command
├── setup.sh                          # Interactive first-run config
├── config.example.yaml               # Template config
├── config.yaml                       # User's config (gitignored)
├── package.json                      # Playwright dependency
├── lib/
│   ├── config.sh                     # Bash config loader
│   ├── config.py                     # Python config loader
│   ├── tier1-fxtwitter.sh            # FxTwitter API extraction
│   ├── tier2-jina.sh                 # Jina Reader fallback + enrichment
│   ├── tier3-playwright.sh           # Playwright single-tweet fallback
│   └── note-generator.py             # Python note template + classifier
├── scripts/
│   ├── extract-bookmarks.js          # Playwright bookmark scroller
│   ├── extract-bookmarks-manual.js   # Browser console version (no Playwright)
│   ├── extract-bookmarks-manual.sh   # Launcher for console version
│   ├── process-bookmarks.sh          # Batch processor with tiered fetch
│   └── export-cookies.sh             # Chrome cookie export helper
├── .claude/
│   └── commands/
│       └── process-bookmarks.md      # Claude Code custom command
├── skills/
│   └── tweet-to-obsidian/
│       ├── SKILL.md                  # Claude Desktop/Code skill
│       └── references/
│           ├── note-template.md
│           └── config-reference.md
├── examples/
│   ├── config-minimal.yaml
│   ├── config-developer.yaml
│   ├── config-researcher.yaml
│   ├── config-news.yaml
│   └── sample-notes/
│       ├── tool-announcement.md
│       ├── thread-example.md
│       └── x-article-example.md
├── README.md
├── LICENSE
└── .gitignore
```

## The Main Entry Point: tweet-to-obsidian.sh

This is what the user runs. One script, handles everything.

```bash
#!/usr/bin/env bash
# tweet-to-obsidian — Turn Twitter bookmarks into Obsidian notes

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/config.sh"
load_config "$SCRIPT_DIR/config.yaml"

case "${1:-}" in
  setup)
    "$SCRIPT_DIR/setup.sh"
    ;;
  extract)
    # Extract bookmark URLs from Twitter
    if [ -f "$SCRIPT_DIR/cookies.json" ]; then
      node "$SCRIPT_DIR/scripts/extract-bookmarks.js" \
        --cookies "$SCRIPT_DIR/cookies.json" \
        --vault "$VAULT_PATH" \
        --output "$BOOKMARKS_DIR/bookmarks.txt"
    else
      "$SCRIPT_DIR/scripts/extract-bookmarks-manual.sh"
    fi
    ;;
  process)
    # Process URLs into vault notes
    "$SCRIPT_DIR/scripts/process-bookmarks.sh" "${2:-}"
    ;;
  cookies)
    # Export Chrome cookies for Playwright
    "$SCRIPT_DIR/scripts/export-cookies.sh"
    ;;
  ""|run)
    # Full pipeline: extract + process
    "$0" extract
    "$0" process
    ;;
  *)
    echo "Usage: tweet-to-obsidian [setup|extract|process|cookies|run]"
    echo ""
    echo "  setup    — Interactive first-run configuration"
    echo "  extract  — Pull bookmark URLs from Twitter"
    echo "  process  — Process URLs into Obsidian notes"
    echo "  cookies  — Export Chrome session cookies for auto-extraction"
    echo "  run      — Full pipeline (extract + process) [default]"
    ;;
esac
```

User experience:
- First time: `./tweet-to-obsidian setup` (prompts for vault path, creates config)
- With cookies: `./tweet-to-obsidian` (fully automated end-to-end)
- Without cookies: `./tweet-to-obsidian extract` (manual console step), then `./tweet-to-obsidian process`
- Just process URLs: `./tweet-to-obsidian process ~/urls.txt`

## config.yaml — Full Schema

```yaml
vault:
  path: "~/Obsidian Vaults/MyVault"       # REQUIRED — vault root
  notes_folder: "Resources"                # Where notes go (relative to vault root)
  default_category: "Inbox"                # Fallback when classification misses

bookmarks:
  dir: "~/Documents/twitter-bookmarks"     # Working directory for URL lists
  batch_size: 10                           # Tweets per batch
  batch_delay: 2                           # Seconds between batches

categories:                                # Folder routing — first keyword match wins
  - name: "AI Tools"
    keywords: ["open-source", "cli", "api", "github", "tool", "library", "model", "llm"]
  - name: "Web Development"
    keywords: ["react", "nextjs", "typescript", "frontend", "css", "tailwind"]
  - name: "AI Agents"
    keywords: ["agent", "multi-agent", "orchestration", "swarm", "autonomous"]
  - name: "Content and Design"
    keywords: ["design", "figma", "brand", "video", "creative", "marketing"]

wikilinks: {}                              # Optional — auto-link vault entities
  # "My Project": "[[My Project]]"
  # "React": "[[React Notes]]"

enrichment:
  enabled: true                            # Fetch linked GitHub READMEs, blog posts
  max_links_per_note: 3                    # Don't fetch more than N linked URLs

template:
  base_tags: ["type/tweet", "source/twitter"]
  include_engagement: true
  include_my_notes: true
  title_mode: "auto"                       # auto = smart extraction, raw = first line
```

## Components to Build (in order)

### 1. setup.sh — Interactive Setup (new)

```
Welcome to tweet-to-obsidian!

Where is your Obsidian vault?
> ~/Obsidian Vaults/MyVault

What folder should notes go in? [Resources]
>

Want to set up topic categories? [Y/n]
> Y

Category name (empty to finish): AI Tools
Keywords (comma-separated): open-source, cli, api, github, tool
Category name: Web Dev
Keywords: react, nextjs, typescript, frontend
Category name:

Want to set up automatic bookmark extraction? [y/N]
(Requires exporting Chrome cookies — we'll walk you through it)
> y

Running cookie export...
[exports cookies]

Done! Run ./tweet-to-obsidian to process your bookmarks.
```

Creates config.yaml from answers. Optionally runs cookie export.

### 2. lib/config.sh + lib/config.py — Config Loaders (refactor)

Extract config loading from process-bookmarks.sh into shared modules.
All scripts source config.sh. Python scripts import config.py.

config.sh exports: VAULT_PATH, NOTES_FOLDER, DEFAULT_CATEGORY, BOOKMARKS_DIR,
BATCH_SIZE, BATCH_DELAY, CATEGORIES (as associative array), WIKILINKS, ENRICHMENT_ENABLED.

### 3. lib/note-generator.py — Standalone Note Generator (refactor)

Extract the embedded Python from process-bookmarks.sh into a standalone module.
Reads config.yaml for categories, wikilinks, template settings, title mode.

Changes from current embedded version:
- Reads categories + keywords from config instead of hardcoded lists
- Smart title generation (see personal plan Bug 1 fix)
- Wikilink injection reads from config
- Tag generation reads from config
- Accepts both JSON (Tier 1) and markdown (Tier 2) input formats
- Outputs the complete note file content to stdout

### 4. scripts/extract-bookmarks.js — Playwright Version (refactor)

Upgrade from browser-console-only to Playwright + browser-console dual mode.

Playwright mode (cookies.json exists):
- Launches headless Chromium with saved session
- Navigates to bookmarks, scrolls, extracts
- Writes URLs to bookmarks.txt
- Returns count

Console mode (no cookies):
- Same as current extract-bookmarks-manual.js
- Copies JS to clipboard for manual paste

### 5. scripts/process-bookmarks.sh — Tiered Fetch (refactor)

Replace single curl with 3-tier extraction:
- Tier 1: FxTwitter curl → JSON
- Tier 2: Jina Reader curl → markdown (fallback)
- Tier 3: Playwright page fetch → HTML parsed to text (ultimate fallback)

Add enrichment step: after note generation, scan tweet for linked URLs,
fetch via Jina, append as "## Linked Content" section.

Add dedup cleanup: remove ALL known-in-vault URLs from bookmarks.txt,
not just freshly processed ones.

### 6. scripts/export-cookies.sh — Cookie Helper (new)

Exports X/Twitter session cookies from Chrome for Playwright use.
Detects cookie staleness (warn if >14 days old).

### 7. tweet-to-obsidian.sh — Main Entry Point (new)

The top-level script that ties everything together.
Subcommands: setup, extract, process, cookies, run (default).

### 8. Example Configs (new)

Four examples showing different use cases:
- minimal: just vault path
- developer: AI tools, web dev, agents, DevOps categories
- researcher: papers, datasets, methods, conferences
- news: politics, tech industry, finance, science

### 9. Sample Output Notes (new)

Three real examples showing what notes look like:
- A tool announcement tweet (simple)
- A thread with multiple parts
- An X Article with full extracted content

### 10. README.md (already written, needs updating)

Update the existing README to reflect the new one-command interface,
cookie setup, and 3-tier architecture. Add the architecture diagram.

### 11. Claude Code Integration (refactor)

Update .claude/commands/process-bookmarks.md to read from config.yaml.
Update skills/tweet-to-obsidian/SKILL.md to reference config.

---

## Build Order for CC

Phase 1 — Core refactoring (1 hour):
1. lib/config.py — Python config loader
2. lib/config.sh — Bash config loader
3. lib/note-generator.py — extract from process-bookmarks.sh, add smart titles
4. config.example.yaml — full schema with docs

Phase 2 — 3-tier extraction (1 hour):
5. lib/tier1-fxtwitter.sh — extract from process-bookmarks.sh
6. lib/tier2-jina.sh — Jina wrapper + enrichment
7. lib/tier3-playwright.sh — Playwright single-tweet fallback
8. Refactor process-bookmarks.sh to use tiered fetch + config

Phase 3 — Playwright bookmark extraction (45 min):
9. scripts/extract-bookmarks.js — Playwright + manual dual mode
10. scripts/export-cookies.sh — cookie helper
11. package.json with Playwright dependency

Phase 4 — User experience (45 min):
12. tweet-to-obsidian.sh — main entry point
13. setup.sh — interactive config wizard
14. Example configs (4 files)
15. Sample output notes (3 files)

Phase 5 — Documentation + packaging (30 min):
16. Update README.md
17. Update SKILL.md and process-bookmarks.md command
18. .gitignore, LICENSE
19. Test end-to-end with clean config

Total: ~4 hours

## Key Differences from Personal Version

| Aspect | Personal | Open Source |
|---|---|---|
| Config | Hardcoded paths and categories | config.yaml with setup wizard |
| Entry point | Separate scripts | One command: `./tweet-to-obsidian` |
| Bookmark extraction | Manual console paste | Playwright automated (with manual fallback) |
| Tweet fetching | FxTwitter only | 3-tier: FxTwitter → Jina → Playwright |
| Titles | Raw tweet first line | Smart extraction (tool names, patterns) |
| Enrichment | None | Jina fetches linked GitHub/blog content |
| Wikilinks | Hardcoded entities | Configurable via config.yaml |
| Categories | Hardcoded 4 folders | User-defined via config.yaml |
| Dedup cleanup | Leaves skipped URLs | Cleans all vault-known URLs |
