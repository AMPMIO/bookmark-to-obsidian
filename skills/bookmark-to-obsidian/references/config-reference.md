# Config Reference

Full documentation for all config.yaml fields.

## Complete Schema

```yaml
vault:
  path: "~/Documents/ObsidianVault"   # REQUIRED — path to vault root
  notes_folder: "Resources"           # subfolder for tweet notes
  default_category: "Inbox"           # fallback when no category matches

bookmarks:
  dir: "~/Documents/twitter-bookmarks"    # working directory
  file: "bookmarks.txt"                   # input file
  processed_file: "bookmarks-processed.txt"  # archive

processing:
  batch_size: 10           # tweets per batch before pausing
  batch_delay_seconds: 2   # pause duration (seconds)

categories:
  - name: "Folder Name"
    keywords:
      - "keyword1"
      - "keyword2"

wikilinks: {}              # dict or list — see below

enrichment:
  enabled: true            # fetch linked content via Jina Reader
  max_links_per_note: 3    # max URLs to enrich per note

template:
  base_tags:
    - "type/tweet"
    - "source/twitter"
  include_engagement: true
  include_my_notes: true
  distillation_start: 0
```

---

## vault

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `path` | string | `~/Documents/ObsidianVault` | Absolute path to vault root. Tilde expanded. |
| `notes_folder` | string | `Resources` | Subfolder inside vault for tweet notes. Created if missing. |
| `default_category` | string | `Inbox` | Fallback folder when no category keyword matches. |

---

## bookmarks

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dir` | string | `~/Documents/twitter-bookmarks` | Directory for bookmark input/output files. |
| `file` | string | `bookmarks.txt` | Input file: one tweet URL per line. |
| `processed_file` | string | `bookmarks-processed.txt` | Archive of processed URLs. |

---

## categories

List of folder routing rules. First match wins. Falls back to `vault.default_category`.

```yaml
categories:
  - name: "AI Tools"          # Folder name (created automatically)
    keywords:
      - "github"              # Case-insensitive substring match against full tweet text
      - "open-source"
```

---

## wikilinks

Auto-link entity names to vault pages. Two supported formats:

**Dict format** (entity → custom target):
```yaml
wikilinks:
  "React": "[[React Notes]]"
  "My Project": "[[My Project MOC]]"
```

**List format** (entity only, auto-wraps in [[entity]]):
```yaml
wikilinks:
  - entity: "React"
  - entity: "TypeScript"
    target: "[[TypeScript Notes]]"  # optional custom target
```

Only the first occurrence of each entity in the tweet text is linked.

---

## enrichment

After generating a note, fetches linked URLs from the tweet text via Jina Reader and appends as `## Linked Content`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable enrichment globally. |
| `max_links_per_note` | int | `3` | Max URLs to fetch per note. |

Twitter/t.co URLs are excluded — only external links (GitHub, blog posts, etc.) are enriched.

---

## template

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `base_tags` | list | `["type/tweet", "source/twitter"]` | Tags added to every note's frontmatter. |
| `include_engagement` | bool | `true` | Show 💬🔁❤️👁🔖 engagement stats. |
| `include_my_notes` | bool | `true` | Add empty `## My Notes` section. |
| `distillation_start` | int | `0` | Initial value of `distillation:` frontmatter field. |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `T2O_CONFIG` | Override config file path. Checked before auto-detection. |
