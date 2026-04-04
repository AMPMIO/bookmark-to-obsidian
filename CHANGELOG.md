# Changelog

All notable changes to bookmark-to-obsidian are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- `tests/test_note_generator.py` — 25 unit tests covering `classify_tweet`, `apply_wikilinks`, `extract_title`, `extract_linked_urls`, and `fmt_number`. Run with `python3 -m unittest discover -s tests -v`.
- `tests/test_integration.py` — 19 integration tests for `generate_from_json` and `generate_from_markdown` using temp files with realistic mock data. Covers: category classification, wikilink application, frontmatter structure, engagement toggle, my_notes toggle, linked URL extraction, error handling (missing file, invalid JSON, non-dict tweet field), Jina content extraction, and markdown generator edge cases.

### Fixed
- `apply_wikilinks()` — placeholder-based linking prevents shorter overlapping entities from being re-matched inside already-linked spans. Previously "React" would be double-linked inside "[[React Native]]"; now placeholders ensure each span is linked at most once.
- `main()` in `lib/note-generator.py` — narrowed `except Exception` to `except (FileNotFoundError, ValueError)` so unexpected errors are not silently swallowed.

### Changed
- `lib/note-generator.py` — extracted `_classify_and_tag()` and `_build_frontmatter()` helpers; `generate_from_json()` and `generate_from_markdown()` now delegate to these shared helpers, eliminating duplicated classify/tag/frontmatter logic.
- `lib/note-generator.py` — added type annotations to all public and private functions; function contracts (input/output types) are now explicit.
- `lib/note-generator.py` — extracted `_format_engagement()`, `_build_quote_section()`, and `_build_article_section()` helpers from `generate_from_json()`; function reduced from ~102 to 61 lines; each section-building concern is now a focused, independently readable function.

---

- **Per-category tags** — each category in config can now include an optional `tags:` list. Tags from the matched category are merged with `template.base_tags` in the note frontmatter (union, no duplicates). Enables topic tag hierarchies (`topic/ai`, `topic/research`) per folder without changing the global template. Example:
  ```yaml
  categories:
    - name: "AI Research"
      keywords: ["llm", "paper"]
      tags: ["topic/ai", "topic/research"]
  template:
    base_tags: ["type/tweet", "source/twitter"]
  # → note tags: [type/tweet, source/twitter, topic/ai, topic/research]
  ```
- Config validation: `categories[N].tags` must be a list if present, with a specific error message on type mismatch.
- `config.example.yaml`: per-category `tags` examples for all default categories; wikilinks documentation explaining longest-first ordering and both dict/list formats.
- SKILL.md: Quick Reference section at top (minimal config → expected note frontmatter); Phase 5 extended with per-category tags pseudo-code and concrete input/output example.

### Changed
- `classify_tweet(text, categories, default)` now returns `(folder_name, category_tags)` — single pass replaces the previous separate `classify()` call + tag lookup.
- `apply_wikilinks()` now sorts entities longest-first before applying. Prevents "React" from matching inside "React Native" when both are configured.
- `generate_from_json()` and `generate_from_markdown()`: raise `FileNotFoundError` (not generic exception) if data file is missing; raise `ValueError` with parse details on malformed JSON; raise `ValueError` if the `tweet` field is not a dict (e.g. null in response).
- Date parsing fallback in `generate_from_json()`: logs a warning to stderr when `created_at` cannot be parsed, instead of silently using today's date.
- Exception handler in `main()` now includes the exception type in the error message (`Error generating note (ValueError): ...`).
- `_expand()` in `config.py`: removed redundant double `expanduser()` call.

---

## [1.1.0] — Stability + Claude Instructions

### Added
- URL normalization: `twitter.com` URLs normalized to `x.com` before dedup comparison.
- Config validation in `lib/config.py`: type checks, required field checks, and range validation with specific error messages.
- `mktemp` failure guard in `process-bookmarks.sh`.
- Tier 1 response validation: rejects FxTwitter responses missing the `tweet` field.
- Tier 2 retry: Jina Reader fetch retries once on failure before falling back to Tier 3.
- JSON parsing consolidated: single Python subprocess call in `process-bookmarks.sh`.

### Changed
- SKILL.md rewritten with 9 comprehensive phases, error table, edge cases, and Obsidian principles.
- `.claude/commands/process-bookmarks.md` updated with troubleshooting table and precise behavior descriptions.

---

## [1.0.0] — Initial Release

### Added
- `scripts/process-bookmarks.sh` — main pipeline.
- `lib/note-generator.py` — note generator from FxTwitter JSON or Jina markdown.
- `lib/config.py` / `lib/config.sh` — YAML config loader with shell export.
- `lib/tier1-fxtwitter.sh`, `lib/tier2-jina.sh`, `lib/tier3-playwright.sh` — fetch tier functions.
- `config.example.yaml` — documented configuration reference.
- `setup.sh` — interactive setup wizard.
- `bookmark-to-obsidian.sh` — single-command entry point.
- `scripts/extract-bookmarks.js` — Playwright automated bookmark extractor.
- `scripts/export-cookies.sh` — Chrome cookie export helper.
- `skills/bookmark-to-obsidian/SKILL.md` — Claude skill for LLM-assisted processing.
- `examples/` — sample notes and config files.
