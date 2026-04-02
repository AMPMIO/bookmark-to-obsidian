# Architecture

bookmark-to-obsidian is a two-component pipeline connected by a plain text file.

```
┌─────────────────────────────────────────────────────────┐
│  Component 1: Bookmark Extractor                        │
│  Runtime: Browser console (x.com/i/bookmarks)           │
│                                                         │
│  extract-bookmarks.sh  →  clipboard (JS snippet)        │
│                              ↓                          │
│                        Browser console                   │
│                        • Scrolls bookmarks page          │
│                        • Extracts tweet URLs             │
│                        • Stops at known vault boundary   │
│                              ↓                          │
│  extract-bookmarks.sh --save  →  bookmarks.txt          │
└─────────────────────────────────────────────────────────┘
                              ↓
                        bookmarks.txt
                    (one URL per line)
                              ↓
┌─────────────────────────────────────────────────────────┐
│  Component 2: Batch Processor                           │
│  Runtime: Terminal (bash + python3)                     │
│                                                         │
│  process-bookmarks.sh                                   │
│  • Reads bookmarks.txt                                  │
│  • Skips URLs already in vault (source: frontmatter)    │
│  • Fetches each tweet via FxTwitter API (no auth)       │
│  • Classifies into folder using config.yaml rules       │
│  • Writes Obsidian markdown note                        │
│  • Moves processed URLs to bookmarks-processed.txt      │
└─────────────────────────────────────────────────────────┘
                              ↓
              Obsidian Vault / notes_folder /
              ├── Category A / Tweet Title.md
              ├── Category B / Tweet Title.md
              └── ...
```

## Key Design Decisions

**No Twitter API key required.** The FxTwitter proxy (`api.fxtwitter.com`) serves public tweet data without authentication. This keeps setup to zero credentials.

**Browser extracts, terminal processes.** The bookmarks page requires your Twitter session cookie — a browser handles this naturally. The processing step is CPU-bound work better done in a terminal script with full filesystem access.

**Plain text handoff.** `bookmarks.txt` is the contract between the two components. It can be manually edited, version-controlled, or populated by other tools.

**Config-driven classification.** Folder routing is a YAML list of keyword rules — no code changes needed to customize for any vault structure. The default config ships with generic categories; users replace them with their own.

**Duplicate detection via frontmatter.** The processor greps `source:` fields from existing notes to build its skip list. No separate database needed — the vault is the source of truth.

## File Roles

| File | Role |
|------|------|
| `config.yaml` | User configuration — vault path, categories, wikilinks |
| `lib/config.py` | Python YAML parser — used by embedded Python in process script |
| `lib/config.sh` | Bash config loader — exports shell variables for scripts |
| `scripts/extract-bookmarks.js` | Browser script — scrolls and extracts tweet URLs |
| `scripts/extract-bookmarks.sh` | Launcher — injects known URLs into JS, handles clipboard I/O |
| `scripts/process-bookmarks.sh` | Main processor — fetches, classifies, writes notes |
| `.claude/commands/process-bookmarks.md` | Claude Code slash command definition |
| `skills/bookmark-to-obsidian/SKILL.md` | Installable Claude skill variant |

## FxTwitter API

Endpoint: `https://api.fxtwitter.com/{username}/status/{tweet_id}`

Returns JSON with full tweet data including:
- `tweet.text` — full text
- `tweet.author` — screen_name, name, followers
- `tweet.likes`, `retweets`, `replies`, `views`, `bookmarks`
- `tweet.created_at` — timestamp
- `tweet.media.all[]` — photos, videos, GIFs
- `tweet.quote` — quoted tweet (recursive structure)
- `tweet.article` — X Article content blocks

No API key or rate limit documented. Batch delay of 2s between groups of 10 is a conservative default.
